# Changelog

## [1.6.6] - 2026-09-03

### Fixed
- **Integracja nie wstawała na Home Assistant 2026.9** — zero encji, wszystkie sensory znikały. `device_info` przekazywało klucz `via_device: None`, a od 2026.9 sama jego obecność kończy się `RuntimeError: ... calls device_registry.async_get_or_create with a deprecated via_device parameter`. Klucz usunięty, bo od początku niczego nie wnosił: licznik gazu nie wisi pod żadnym urządzeniem nadrzędnym

## [1.6.5] - 2026-09-01

### Fixed
- **Logowanie przestało działać — ORLEN wymusił 2FA.** Ekran Keycloaka `required-action?execution=sms-2fa-manage` nie ma już przycisku „Pomiń" (`CANCEL_2FA`); zostało wyłącznie `ENABLE_2FA`. Dokładnie to, co 1.6.3 zapowiadał w „Known issues". Integracja rejestruje teraz konto w 2FA i prosi o kod SMS przez standardowe ponowne uwierzytelnienie Home Assistanta
- **Lawina nieudanych logowań.** Sześć sensorów ponawiało niezależnie co 15 minut, więc przy zepsutym logowaniu integracja wykonywała **24 próby na godzinę** — zmierzone na żywym dzienniku: około 170 w ciągu doby. Jeden obiekt API na wpis konfiguracji plus bezpiecznik w warstwie logowania: po nieudanej próbie kolejne odbijają się bez ruszania sieci
- Ponawianie odświeżania rośnie wykładniczo (15 → 30 → 60 → 120 min, do 8 godzin) zamiast stałych 15 minut. Licznik zeruje się po pierwszym udanym odczycie

### Added
- Krok konfiguracji **„Kod SMS z ORLEN ID"** — pojawia się jako powiadomienie „Wymagane ponowne uwierzytelnienie", gdy ORLEN poprosi o kod
- **Zapamiętywanie sesji.** Ciasteczka po udanym logowaniu trafiają do wpisu konfiguracji, więc jeśli Keycloak uzna urządzenie za zaufane, kolejne logowania — także po restarcie HA — idą bez SMS-a
- Testy bezpiecznika logowania i rozpoznawania ekranów Keycloaka (`tests/test_login_backoff.py`), działające bez środowiska Home Assistanta

### Verified
- Pierwsze logowanie z kodem SMS przeszło na żywym koncie (2026-09-01): wszystkie sześć sensorów wróciło z danymi, a integracja zapisała **13 ciasteczek sesji** Keycloaka (`AUTH_SESSION_ID`, `KC_AUTH_SESSION_HASH`, `KC_RESTART`) do wpisu konfiguracji. Czy ORLEN uzna to za zaufane urządzenie i pozwoli pominąć SMS przy kolejnym logowaniu — okaże się przy najbliższym restarcie HA

### Known issues
- Ekran z polem na kod nie został jeszcze zobaczony na żywo — pole rozpoznajemy po tym, że jest **widoczne** (a nie po nazwie), bo nazwy różnią się między wersjami Keycloaka. Gdyby ORLEN zbudował ten ekran nietypowo, w dzienniku wyląduje zrzut całej strony i poprawka będzie kwestią jednej linii
- Metoda **eBOK Login** nie przechodzi przez ORLEN ID i nie wymaga kodu SMS. Jeśli konto ma jeszcze stary identyfikator i PIN, jest to najprostsza droga w ogóle bez 2FA

## [1.6.4] - 2026-07-28

### Note
- Wyłącznie bump wersji, bez zmian w kodzie — 1.6.3 zawierał już wszystkie poprawki (zweryfikowany bajt po bajcie w opublikowanym ZIP-ie), ale HACS u części instalacji pokazywał wciąż lokalnie zainstalowaną wcześniej wersję beta. Nowy numer wymusza jednoznaczną, nowszą wersję do pobrania.

## [1.6.3] - 2026-07-28

### Fixed
- `myorlen_api.py`: logowanie zaczęło zwracać "Login failed: No token received" — ORLEN wstawił między podaniem hasła a przekierowaniem na `/home` nowy ekran Keycloak „Czy chcesz włączyć dwustopniowe logowanie?". Logowanie automatycznie pomija ten ekran (POST z polem `CANCEL_2FA`, tak jak kliknięcie „Pomiń" w przeglądarce).

### Added
- Karta urządzenia w HA pokazuje teraz numer zainstalowanej wersji integracji (czytany z `manifest.json`, zawsze zgodny z rzeczywistością)

### Known issues
- ORLEN zapowiada, że 2FA stanie się obowiązkowe — gdy przycisk „Pomiń" zniknie z tego ekranu, to obejście przestanie działać i integracja będzie wymagała innego mechanizmu logowania (np. kodu SMS lub kodu TOTP z aplikacji)

## [1.6.2] - 2026-04-07

### Fixed
- Sensor "Tracking kosztów": wartość zaokrąglona do 4 miejsc po przecinku (format `x.xxxx`) zamiast pełnej precyzji float

## [1.6.1] - 2026-04-04

### Fixed
- `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` przy pustej lub błędnej odpowiedzi API myORLEN: dodano sprawdzenie pustej odpowiedzi i nieoczekiwanego kodu HTTP w `_authenticated_get()` — zamiast traceback z JSONDecodeError logowany jest czytelny komunikat błędu

## [1.6.0] - 2026-04-03

### Added
- Sensor Stan Licznika: nowe atrybuty `reading_date_local`, `reading_type`, `reading_status` z ostatniego odczytu
- Sensor Faktura: nowy atrybut `days_remaining_to_deadline` — liczba dni do terminu płatności najbliższej nieopłaconej faktury
- Wszystkie sensory: atrybuty `tariff` i `contract_number` pobierane z listy liczników (`get-ppg-list`)

## [1.5.0] - 2026-03-31

### Fixed
- `ppg_reading_for_meter.py`: pole `Value: null` w API powodowało wyświetlanie "nieznany" dla sensora Stan Licznika; `PpId: null` i null daty powodowały crash parsera
- `invoices.py`: null daty w odpowiedzi API powodowały crash parsowania listy faktur
- Każde wywołanie `invoices()` / `readingForMeter()` wykonywało pełny OAuth login od nowa — 6 sensorów przy starcie robiło równoległe loginy, co powodowało wyścig i część sensorów (m.in. Conversion Factor) dostawała pusty token → "nieznany"

### Added
- Cachowanie tokenu autoryzacji w `myORLENApi` — token reużywany między wywołaniami, automatyczne odświeżenie przy HTTP 401
- Mechanizm retry: gdy sensor zwraca `nieznany` lub wystąpi błąd API, automatyczna ponowna próba po 15 minutach (zamiast czekania 8 godzin)

## [1.4.1] - 2026-03-31

### Fixed
- Sensor kosztów (i pozostałe sensory oparte o faktury) przestawał działać gdy API zwróciło `GrossAmount: null` — `float(None)` rzucał `TypeError` przerywając parsowanie całej listy faktur
- Dodano obsługę wyjątków w `async_update` wszystkich sensorów — błąd sieciowy lub wygasły token zachowuje teraz ostatnią poprawną wartość zamiast przestawiać sensor na `unavailable`

## [1.4.0] - 2026-03-31

### Dodano
- Sensor **Last Invoice Wear M3** — zużycie gazu z ostatniej faktury w m³
- Sensor **Last Invoice Wear KWH** — zużycie gazu z ostatniej faktury w kWh
- Sensor **Conversion Factor** — współczynnik konwersji gazu (kWh/m³) obliczany z ostatniej faktury; atrybuty: numer faktury, data wystawienia, wartości m³ i kWh

## [1.3.1] - 2026-03-24

### Zmieniono
- Workflow commituje zaktualizowany manifest.json z powrotem do repo

## [1.3.0] - 2026-03-24

### Zmieniono
- Przepisano workflow release — działa na Forgejo i tworzy release na GitHub
- Zastąpiono zewnętrzne akcje czystym curl + python

## [1.2.9] - 2026-03-07

### Zmieniono
- Refaktoryzacja kodu dla lepszej czytelności

## [1.2.8] - 2026-03-07

### Zmieniono
- Uproszczono codeowners i integration_type w manifest.json

## [1.2.7] - 2026-03-07

### Zmieniono
- Klasa bazowa sensor, f-stringi, uproszczenie invoices.py

## [1.2.6] - 2026-02-25

### Zmieniono
- Refaktoryzacja struktury kodu

## [1.2.5] - 2026-02-25

### Zmieniono
- Bump wersji do 1.2.5

## [1.2.4] - 2026-02-24

### Zmieniono
- Aktualizacja nazw metod uwierzytelniania na małe litery

## [1.2.2] - 2026-02-22

### Dodano
- Pole metody uwierzytelniania w tłumaczeniach

## [1.2.1] - 2026-02-22

### Zmieniono
- Bump wersji do 1.2.1

## [1.1.1] - 2026-02-22

### Zmieniono
- Refaktoryzacja manifest.json

## [1.0.0] - 2026-02-22

### Dodano
- Pierwsze wydanie
- Pobieranie danych licznika gazu z myORLEN
- Sensory: stan licznika, faktura, koszt śledzenia
