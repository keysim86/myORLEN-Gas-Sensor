"""Bezpiecznik logowania i przejscie przez 2FA.

Te testy NIE potrzebuja Home Assistanta -- myorlen_api nie importuje go wcale.
Dzieki temu najbardziej ryzykowna czesc zmiany z 2026-09-01 (przerwa po bledzie
i rozpoznawanie ekranow Keycloaka) da sie sprawdzic bez calego srodowiska.
"""

import pytest

from custom_components.myorlen_gas_sensor.myorlen_api import (
    LOGIN_COOLDOWN_MAX,
    LOGIN_COOLDOWN_START,
    LoginCooldown,
    SmsCodeRequired,
    myORLENApi,
)

# Strona, ktora ORLEN pokazal 2026-09-01 zamiast zalogowania. Znaczniki
# przepisane ze zrzutu z dziennika: jeden formularz, jedno pole, zaden przycisk
# "Pomin". Reszta strony (naglowki, skrypty) pominieta -- nie ma wplywu.
STRONA_WYMUSZONEGO_2FA = """
<form action="https://oid-ws.orlen.pl/realms/oid/login-actions/required-action?session_code=ABC&amp;execution=sms-2fa-manage" method="post">
    <input type="hidden" name="session_code" value="ABC"/>
    <p>Od teraz bedziesz otrzymywac kody SMS podczas logowania.</p>
    <input type="submit" name="ENABLE_2FA" value="Wlacz"/>
</form>
"""

# Ekran z kodem. UWAGA: to REKONSTRUKCJA typowej strony Keycloaka, a nie zrzut
# z ORLEN-u -- w chwili pisania nikt jeszcze przez ten ekran nie przeszedl.
# Test pilnuje wiec ZASADY ("wybierz jedyne widoczne pole"), a nie konkretnej
# nazwy pola. Gdy zobaczymy prawdziwa strone, fixture nalezy podmienic.
STRONA_Z_KODEM = """
<form action="https://oid-ws.orlen.pl/realms/oid/login-actions/required-action?session_code=XYZ" method="post">
    <input type="hidden" name="session_code" value="XYZ"/>
    <input type="hidden" name="execution" value="sms-2fa-challenge"/>
    <input type="text" name="smsCode" autocomplete="one-time-code"/>
    <input type="submit" name="login" value="Potwierdz"/>
</form>
"""


def _api() -> myORLENApi:
    return myORLENApi("kto@example.com", "tajne")


def test_pierwsze_niepowodzenie_wlacza_przerwe():
    api = _api()
    api.login = lambda: ""
    assert api._login_guarded() == ""
    assert api.seconds_until_login_allowed() > 0


def test_przerwa_rosnie_wykladniczo_i_ma_sufit():
    api = _api()
    api.login = lambda: ""
    dlugosci = []
    for _ in range(8):
        api._login_blocked_until = 0.0
        api._login_guarded()
        dlugosci.append(api.seconds_until_login_allowed())
    assert dlugosci[0] <= LOGIN_COOLDOWN_START
    assert dlugosci[1] > dlugosci[0]
    assert dlugosci[2] > dlugosci[1]
    assert max(dlugosci) <= LOGIN_COOLDOWN_MAX


def test_w_przerwie_nie_ma_ani_jednego_zapytania():
    """Sedno poprawki: szesc sensorow nie zamienia sie w szesc logowan."""
    api = _api()
    prob = {"ile": 0}

    def nieudane():
        prob["ile"] += 1
        return ""

    api.login = nieudane
    api._login_guarded()
    for _ in range(20):
        with pytest.raises(LoginCooldown):
            api._login_guarded()
    assert prob["ile"] == 1


def test_udane_logowanie_kasuje_przerwe():
    api = _api()
    api.login = lambda: ""
    api._login_guarded()
    assert api.seconds_until_login_allowed() > 0
    api.login = lambda: "token"
    api._login_blocked_until = 0.0
    assert api._login_guarded() == "token"
    assert api.seconds_until_login_allowed() == 0


def test_czekanie_na_sms_wstrzymuje_kolejne_logowania():
    """Bo inaczej kazdy sensor zamowilby wlasnego SMS-a."""
    api = _api()
    api._pending_2fa = {"session": None, "url": "u", "field": "smsCode"}
    for _ in range(5):
        with pytest.raises(SmsCodeRequired):
            api._login_guarded()


def test_ekran_wymuszonego_2fa_nie_ma_pola_na_kod():
    api = _api()
    assert api._znajdz_pole_kodu(STRONA_WYMUSZONEGO_2FA) is None


def test_znajduje_pole_na_kod_a_nie_session_code():
    """session_code ma w nazwie 'code' i jest ukryte. Bez odrzucania pol
    technicznych wpisywalibysmy kod SMS w pole sesji."""
    api = _api()
    znalezione = api._znajdz_pole_kodu(STRONA_Z_KODEM)
    assert znalezione is not None
    akcja, pole = znalezione
    assert pole == "smsCode"
    assert "session_code=XYZ" in akcja


def test_reset_backoff_odblokowuje_na_zyczenie_czlowieka():
    api = _api()
    api.login = lambda: ""
    api._login_guarded()
    assert api.seconds_until_login_allowed() > 0
    api.reset_backoff()
    assert api.seconds_until_login_allowed() == 0


def test_zestarzale_ciasteczka_nie_blokuja_logowania():
    """Zapisana sesja to optymalizacja, nie warunek.

    Zestarzale ciasteczka Keycloaka potrafia wpedzic logowanie w petle
    przekierowan; wtedy trzeba je wyrzucic i sprobowac od zera, a nie
    polec. 2026-09-03 wlasnie to zatrzymalo cala integracje."""
    api = _api()
    api._session = object()          # udajemy zapisana sesje
    wyczyszczone = []
    api._on_session_saved = wyczyszczone.append
    proby = []

    def _oid(sesja):
        proby.append(sesja)
        if sesja is not None:
            raise Exception("Exceeded 30 redirects")
        return "token-po-czystym-logowaniu"

    api._login_oid = _oid
    assert api.login() == "token-po-czystym-logowaniu"
    assert len(proby) == 2                   # najpierw z sesja, potem bez
    assert proby[1] is None
    assert wyczyszczone == [{}]              # ciasteczka skasowane we wpisie
    assert api._session is None


def test_bez_zapisanej_sesji_blad_leci_dalej():
    """Bez ciasteczek nie ma czego czyscic -- drugiej proby byc nie moze,
    inaczej kazde nieudane logowanie szlo by do ORLEN-u podwojnie."""
    api = _api()
    api._session = None
    proby = []

    def _oid(sesja):
        proby.append(sesja)
        raise Exception("cokolwiek")

    api._login_oid = _oid
    try:
        api.login()
    except Exception:
        pass
    assert len(proby) == 1
