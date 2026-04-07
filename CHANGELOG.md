# Changelog

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
