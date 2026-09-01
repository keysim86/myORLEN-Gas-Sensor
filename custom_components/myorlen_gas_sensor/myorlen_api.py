import re
import string
import logging
import time

import requests


from .invoices import invoices_from_dict, Invoices
from .pgp_list import (PpgList, ppg_list_from_dict)
from .ppg_reading_for_meter import PpgReadingForMeter, ppg_reading_for_meter_from_dict

login_url = "https://ebok.myorlen.pl/auth/login?api-version=3.0"
devices_list_url = "https://ebok.myorlen.pl/crm/get-ppg-list?api-version=3.0"
readings_url = "https://ebok.myorlen.pl/crm/get-all-ppg-readings-for-meter?pageSize=10&pageNumber=1&api-version=3.0&idPpg="
invoices_url = "https://ebok.myorlen.pl/crm/get-invoices-v2?pageNumber=1&pageSize=12&api-version=3.0"
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
}

_LOGGER = logging.getLogger(__name__)

AUTH_METHOD_ORLEN_ID = "orlen_id"
AUTH_METHOD_EBOK = "login_ebok"

HOME_URL = "https://ebok.myorlen.pl/home"
OID_DEVICE_ID = "a908313085dd4f16deaa4c15897e755e"

# PRZERWA PO NIEUDANYM LOGOWANIU. Powod, dla ktorego to w ogole istnieje:
# 2026-09-01 integracja wykonala okolo 170 nieudanych logowan w ciagu dnia,
# 24 na godzine. Nie bylo to zadne szalenstwo w kodzie logowania, tylko
# SZESC SENSOROW ponawiajacych niezaleznie co 15 minut. Dopoki logowanie
# dzialalo, nikt tego nie widzial -- token byl w pamieci i sensory go tylko
# odczytywaly. Gdy logowanie zaczelo padac, kazde ponowienie bylo osobnym
# uderzeniem w Keycloaka ORLEN-u. Tak wlasnie blokuje sie konta.
#
# Bezpiecznik siedzi TUTAJ, a nie w sensorach, bo tylko tutaj nie da sie go
# obejsc: kazda droga do danych prowadzi przez token, a kazdy token przez
# to miejsce. Sensory moga sie ponawiac ile chca -- po pierwszym niepowodzeniu
# dostana wyjatek bez ruszania sieci.
LOGIN_COOLDOWN_START = 900          # 15 minut po pierwszym niepowodzeniu
LOGIN_COOLDOWN_MAX = 8 * 3600       # nie rzadziej niz normalny cykl odswiezania


class SmsCodeRequired(Exception):
    """Keycloak poprosil o kod SMS i czekamy, az poda go czlowiek.

    To NIE JEST awaria logowania i nie wlacza przerwy karnej -- ale wstrzymuje
    kolejne proby, zeby szesc sensorow nie wyslalo szesciu SMS-ow pod rzad.
    """


class LoginCooldown(Exception):
    """Poprzednie logowanie padlo; nie pukamy do ORLEN-u przed koncem przerwy."""


class myORLENApi:

    def __init__(self, username, password, auth_method=AUTH_METHOD_ORLEN_ID,
                 on_session_saved=None) -> None:
        self.username = username
        self.password = password
        self.auth_method = auth_method
        self._cached_token = None
        # Sesja przezywa udane logowanie. Jesli Keycloak wystawi ciasteczko
        # zaufanego urzadzenia, kolejne logowania pojda bez SMS-a. Wywolanie
        # zwrotne pozwala integracji zapisac ciasteczka do wpisu konfiguracji,
        # zeby przezyly takze restart HA -- bez tego kazdy restart to nowy SMS.
        self._session = None
        self._on_session_saved = on_session_saved
        # Trwa czekanie na kod SMS: sesja, adres formularza i nazwa pola.
        self._pending_2fa = None
        self._login_failures = 0
        self._login_blocked_until = 0.0
        # Podpinane przez integracje: budzi w HA prosbe o kod SMS. Wolane
        # RAZ, w chwili gdy Keycloak pokaze formularz -- nie przy kazdej
        # kolejnej probie, bo tych po drodze bedzie szesc na cykl.
        self.on_sms_required = None

    # ---- ciasteczka: przetrwanie restartu ----

    def export_cookies(self) -> dict:
        if not self._session:
            return {}
        return requests.utils.dict_from_cookiejar(self._session.cookies)

    def import_cookies(self, jar: dict) -> None:
        if not jar:
            return
        self._session = self._new_session()
        requests.utils.add_dict_to_cookiejar(self._session.cookies, jar)

    def _new_session(self):
        session = requests.Session()
        session.headers.update({
            'User-Agent': headers['User-Agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/avif,image/webp,image/apng,*/*;q=0.8',
        })
        return session

    def _zapisz_sesje(self, session):
        self._session = session
        if self._on_session_saved:
            try:
                self._on_session_saved(self.export_cookies())
            except Exception as e:  # zapis ciasteczek nie moze wywrocic logowania
                _LOGGER.debug("Nie udalo sie zapisac ciasteczek sesji: %s", e)

    # ---- bezpiecznik logowania ----

    def seconds_until_login_allowed(self) -> int:
        """Ile sekund zostalo do konca przerwy. Sensory ustawiaja na to ponowienie."""
        return max(0, int(self._login_blocked_until - time.monotonic()))

    def _note_login_failure(self):
        self._login_failures += 1
        przerwa = min(LOGIN_COOLDOWN_START * (2 ** (self._login_failures - 1)),
                      LOGIN_COOLDOWN_MAX)
        self._login_blocked_until = time.monotonic() + przerwa
        _LOGGER.warning(
            "Logowanie do myORLEN nieudane (%d. raz z rzedu). Nastepna proba nie "
            "wczesniej niz za %d min.", self._login_failures, przerwa // 60)

    def _login_guarded(self) -> str:
        if self._pending_2fa:
            raise SmsCodeRequired(
                "Logowanie czeka na kod SMS. Podaj go w Ustawienia -> Urzadzenia "
                "i uslugi -> myORLEN -> Skonfiguruj ponownie.")
        pozostalo = self.seconds_until_login_allowed()
        if pozostalo:
            raise LoginCooldown(
                "Przerwa po nieudanym logowaniu, zostalo %d min." % (pozostalo // 60))
        try:
            token = self.login()
        except SmsCodeRequired:
            raise
        except Exception:
            self._note_login_failure()
            raise
        if token:
            self._login_failures = 0
            self._login_blocked_until = 0.0
        else:
            self._note_login_failure()
        return token

    def _get_token(self) -> str:
        if not self._cached_token:
            self._cached_token = self._login_guarded()
        return self._cached_token

    def _get_token_fresh(self) -> str:
        self._cached_token = self._login_guarded()
        return self._cached_token

    def _authenticated_get(self, url: str):
        """GET with cached token; retries once with fresh login on 401."""
        token = self._get_token()
        if not token:
            raise Exception("Login failed: no token received")
        response = requests.get(url, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'AuthToken': token,
        })
        if response.status_code == 401:
            token = self._get_token_fresh()
            if not token:
                raise Exception("Re-login failed: no token received")
            response = requests.get(url, headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'AuthToken': token,
            })
        if not response.text or not response.text.strip():
            raise Exception(f"Empty response from API (status {response.status_code}): {url}")
        if response.status_code not in (200, 201):
            raise Exception(f"API error {response.status_code}: {response.text[:200]}")
        return response

    def meterList(self) -> PpgList:
        token = self._get_token_fresh()
        if not token:
            raise Exception("Login failed: No token received")

        response = requests.get(devices_list_url, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'AuthToken': token
        })
        data = response.json()
        if data is None or "PpgList" not in data:
            raise Exception("Invalid API response: PpgList missing")
        return ppg_list_from_dict(data)

    def readingForMeter(self, meter_id) -> PpgReadingForMeter:
        return ppg_reading_for_meter_from_dict(self._authenticated_get(readings_url + meter_id).json())

    def invoices(self) -> Invoices:
        return invoices_from_dict(self._authenticated_get(invoices_url).json())

    def login(self) -> string:
        if self.auth_method == AUTH_METHOD_EBOK:
            payload = {
                "identificator": self.username,
                "accessPin": self.password,
                "rememberLogin": "false",
                "DeviceId": "123",
                "DeviceName": "Home Assistant: 99.9.999.99<br>",
                "DeviceType": "Web"
            }
            response = requests.post(login_url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json().get('Token')
            _LOGGER.error("eBOK Login failed. Status: %s, Response: %s", response.status_code, response.text)
            return ""

        init_url = 'https://ebok.myorlen.pl/auth/oid/init-login?api-version=3.0'

        # Sesja z poprzedniego udanego logowania, jesli jakas jest. To ona
        # niesie ewentualne ciasteczko zaufanego urzadzenia od Keycloaka.
        session = self._session or self._new_session()
        init_data = {
            "DeviceId": OID_DEVICE_ID,
            "DeviceType": "Web",
            "DeviceName": "HomeAssistant wersja: 0.1",
            "LightweightRedirectUrl": "https://ebok.myorlen.pl/?show=modal",
            "FinalizeRegistrationRedirectUrl": "https://ebok.myorlen.pl/aktywuj-oid/"
        }

        response_init = session.post(init_url, json=init_data)
        redirect_url = response_init.json().get('RedirectUrl')
        response_page = session.get(redirect_url)

        # NAGRODA ZA TRZYMANIE SESJI: gdy ciasteczka jeszcze zyja, Keycloak
        # przepuszcza od razu na /home i nie ma zadnego formularza -- ani hasla,
        # ani kodu SMS. Wlasnie po to sesja przezywa restart HA.
        if HOME_URL in response_page.url:
            _LOGGER.debug("Zalogowano ciasteczkami z poprzedniej sesji, bez formularza")
            return self._token_from_session(session)

        match = re.search(r'action="([^"]+)"', response_page.text)
        if not match:
            _LOGGER.error("Failed to find action URL in response page")
            return ""

        post_url = match.group(1).replace('&amp;', '&')
        final_response = session.post(post_url, data={
            'username': self.username,
            'password': self.password,
            'credentialId': '',
        })

        # Moze podniesc SmsCodeRequired -- i wtedy czekamy na czlowieka.
        final_response = self._przejdz_przez_2fa(session, final_response)

        if HOME_URL in final_response.url:
            return self._token_from_session(session)

        self._zrzuc_diagnostyke(final_response)
        return ""

    # ------------------------------------------------------------------
    #  DWUSKLADNIKOWE UWIERZYTELNIANIE
    # ------------------------------------------------------------------
    #
    # 2026-09-01 ORLEN zamknal furtke, ktora ta integracja dotad omijala.
    # Wczesniej Keycloak pokazywal ekran "wlaczyc 2FA?" z przyciskiem Pomin
    # (pole CANCEL_2FA) i wystarczylo go klikac. Teraz na stronie
    # required-action?execution=sms-2fa-manage jest DOKLADNIE JEDNO pole:
    # przycisk ENABLE_2FA. Zadnego Pomin, zadnego linku w bok -- sprawdzone
    # zrzutem strony z dziennika (5233 znaki, "Possible skip/cancel links: []").
    #
    # Wobec tego rejestrujemy sie w 2FA i prosimy czlowieka o kod z SMS-a.
    #
    # KLIKNIECIE "WLACZ" WYSYLA SMS, wiec MOZE PASC TYLKO RAZ. Pilnuje tego
    # _pending_2fa: dopoki nie ma kodu, kazde kolejne logowanie konczy sie
    # natychmiastowym SmsCodeRequired bez ruszania sieci. Bez tego szesc
    # sensorow wyslaloby szesc SMS-ow pod rzad na telefon wlasciciela konta.

    # Pola formularza Keycloaka, ktore NIE SA polem na kod, choc nazwa myli.
    # "session_code" ma w nazwie "code" i jest ukryte -- bez tej listy
    # wpisywalibysmy kod SMS w pole sesji i logowanie padaloby bez powodu.
    _POLA_TECHNICZNE = {"session_code", "execution", "tab_id", "client_id",
                        "client_data", "credentialId", "login"}
    _TYPY_WIDOCZNE = {"text", "tel", "number", "password", ""}

    def _znajdz_pole_kodu(self, html: str):
        """Zwraca (adres formularza, nazwa pola) dla ekranu z kodem albo None.

        Nie zgadujemy po nazwie pola, tylko po tym, ze jest WIDOCZNE. Strony
        Keycloaka z kodem maja dokladnie jedno pole do wpisania czegokolwiek,
        a reszta to ukryte pola techniczne. Nazwa bywa rozna miedzy wersjami
        i motywami, widocznosc nie."""
        for form in re.finditer(r'<form[^>]*action="([^"]+)"[^>]*>(.*?)</form>',
                                html, re.DOTALL | re.IGNORECASE):
            akcja, srodek = form.group(1).replace('&amp;', '&'), form.group(2)
            for pole in re.finditer(r'<input\b([^>]*)>', srodek, re.IGNORECASE):
                atrybuty = pole.group(1)
                nazwa = re.search(r'name="([^"]*)"', atrybuty, re.IGNORECASE)
                typ = re.search(r'type="([^"]*)"', atrybuty, re.IGNORECASE)
                if not nazwa:
                    continue
                nazwa = nazwa.group(1)
                typ = (typ.group(1).lower() if typ else "")
                if typ not in self._TYPY_WIDOCZNE or nazwa in self._POLA_TECHNICZNE:
                    continue
                _LOGGER.debug("Ekran z kodem: pole %r, formularz %s", nazwa, akcja)
                return akcja, nazwa
        return None

    def _przejdz_przez_2fa(self, session, resp):
        if HOME_URL in resp.url:
            return resp

        # 1. Stary ekran z przyciskiem Pomin. ORLEN go usunal, ale gdyby wrocil,
        #    to nadal najtansza droga -- bez SMS-a i bez udzialu czlowieka.
        pomin = re.search(r'<form[^>]*action="([^"]+)"[^>]*>.*?name="CANCEL_2FA"',
                          resp.text, re.DOTALL)
        if pomin:
            resp = session.post(pomin.group(1).replace('&amp;', '&'),
                                data={"CANCEL_2FA": "Pomiń"})
            if HOME_URL in resp.url:
                return resp

        # 2. Wymuszona rejestracja w 2FA.
        wlacz = re.search(r'<form[^>]*action="([^"]+)"[^>]*>.*?name="ENABLE_2FA"',
                          resp.text, re.DOTALL)
        if wlacz:
            _LOGGER.info("ORLEN wymusza rejestracje 2FA -- klikam Wlacz, przyjdzie SMS")
            resp = session.post(wlacz.group(1).replace('&amp;', '&'),
                                data={"ENABLE_2FA": "Włącz"})

        # 3. Ekran z kodem -- czy to po rejestracji, czy przy kazdym logowaniu.
        pole = self._znajdz_pole_kodu(resp.text)
        if pole:
            self._pending_2fa = {"session": session, "url": pole[0], "field": pole[1]}
            if self.on_sms_required:
                try:
                    self.on_sms_required()
                except Exception as e:
                    _LOGGER.error("Nie udalo sie poprosic o kod SMS w HA: %s", e)
            raise SmsCodeRequired(
                "ORLEN wyslal kod SMS. Podaj go w Ustawienia -> Urzadzenia i uslugi "
                "-> myORLEN -> Skonfiguruj ponownie.")
        return resp

    def submit_sms_code(self, code: str) -> str:
        """Wysyla kod z SMS-a i konczy logowanie. Wolane z przeplywu konfiguracji."""
        if not self._pending_2fa:
            raise Exception("Zadne logowanie nie czeka teraz na kod SMS.")
        czeka = self._pending_2fa
        session = czeka["session"]
        resp = session.post(czeka["url"], data={czeka["field"]: code.strip()})

        if HOME_URL in resp.url:
            self._pending_2fa = None
            self._login_failures = 0
            self._login_blocked_until = 0.0
            self._cached_token = self._token_from_session(session)
            return self._cached_token

        # Zly albo przeterminowany kod. Keycloak oddaje te sama strone,
        # ale z NOWYM session_code w adresie formularza -- trzeba go odswiezyc,
        # inaczej druga proba poleci na zuzyty formularz i padnie niezaleznie
        # od tego, co czlowiek wpisze.
        pole = self._znajdz_pole_kodu(resp.text)
        if pole:
            self._pending_2fa = {"session": session, "url": pole[0], "field": pole[1]}
            raise Exception("Kod nie zostal przyjety. Sprawdz go i sprobuj ponownie.")
        self._pending_2fa = None
        raise Exception(
            "Kod nie zostal przyjety, a ORLEN nie pokazuje juz formularza. "
            "Zacznij logowanie od nowa.")

    def waiting_for_sms(self) -> bool:
        return self._pending_2fa is not None

    def reset_backoff(self) -> None:
        """Kasuje przerwe karna. Wolane, gdy czlowiek SAM wchodzi w logowanie --
        bezpiecznik ma chronic przed maszyna pukajaca w kolko, a nie przed
        uzytkownikiem, ktory wlasnie kliknal 'Skonfiguruj ponownie'."""
        self._login_failures = 0
        self._login_blocked_until = 0.0

    def _token_from_session(self, session) -> str:
        self._zapisz_sesje(session)
        auth_token_url = (f'https://ebok.myorlen.pl/auth/get-auth-token'
                          f'?deviceId={OID_DEVICE_ID}&api-version=3.0')
        session.headers.update({'Referer': 'https://ebok.myorlen.pl/'})
        res_auth = session.get(auth_token_url)
        if res_auth.status_code == 200:
            return res_auth.json().get('Token')
        _LOGGER.error("Auth token request failed. Status: %s, Response: %s",
                      res_auth.status_code, res_auth.text[:500])
        return ""

    def _zrzuc_diagnostyke(self, resp):
        """Logowanie nie doszlo do /home i nie rozpoznalismy strony.

        Zrzut calej strony jest tu celowo: to on pozwolil ustalic, ze przycisk
        Pomin zniknal i ze zostal sam ENABLE_2FA. Gdy ORLEN znowu cos zmieni,
        bedzie to widac w dzienniku, zamiast zgadywac."""
        body = resp.text
        _LOGGER.error(
            "Login did not redirect to /home. Final URL: %s, Status: %s, Body length: %s",
            resp.url, resp.status_code, len(body))
        forms = re.findall(r'<form[^>]*action="([^"]+)"[^>]*>', body)
        _LOGGER.error("Forms found on page: %s", [f.replace('&amp;', '&') for f in forms])
        for i in range(0, len(body), 1800):
            _LOGGER.error("Body[%05d]: %s", i, body[i:i + 1800])
