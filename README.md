[![GitHub Latest Release][releases_shield]][latest_release]
[![GitHub All Releases][downloads_total_shield]][releases]
[![HACS][hacs_shield]][hacs]

[releases_shield]: https://img.shields.io/github/release/keysim86/myORLEN-Gas-Sensor.svg?style=popout
[latest_release]: https://github.com/keysim86/myORLEN-Gas-Sensor/releases/latest
[releases]: https://github.com/keysim86/myORLEN-Gas-Sensor/releases
[downloads_total_shield]: https://img.shields.io/github/downloads/keysim86/myORLEN-Gas-Sensor/total
[hacs_shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=popout
[hacs]: https://hacs.xyz

# myORLEN Gas Sensor

Integracja do Home Assistant pobierająca dane o zużyciu gazu dla klientów myORLEN / PGNiG.

Dane są pobierane z API serwisu [ebok.myorlen.pl](https://ebok.myorlen.pl).

## Sensory

Na każdy licznik gazowy tworzone jest 6 sensorów:

| Sensor | Jednostka | Opis |
|--------|-----------|------|
| **Stan licznika** | m³ | Aktualny odczyt licznika gazu. Atrybuty: zużycie od ostatniego odczytu, data odczytu, typ odczytu, status, taryfa, numer umowy. |
| **Należności** | PLN | Kwota najbliższej nieopłaconej faktury. Atrybuty: termin płatności, kwota, zużycie m³/kWh, dni do terminu, taryfa, numer umowy. |
| **Tracking kosztów** | PLN/m³ | Koszt gazu z ostatniej faktury (kwota brutto ÷ zużycie m³), zaokrąglony do 4 miejsc po przecinku. Przydatny w panelu Energii do śledzenia kosztów. Atrybuty: data faktury, kwota brutto, zużycie m³/kWh, numer faktury, taryfa, numer umowy. |
| **Zużycie (faktura) m³** | m³ | Zużycie gazu z ostatniej faktury z prawidłowymi danymi. Atrybuty: numer faktury, data, okres rozliczeniowy, taryfa, numer umowy. |
| **Zużycie (faktura) kWh** | kWh | Zużycie gazu z ostatniej faktury w kWh. Atrybuty: numer faktury, data, okres rozliczeniowy, taryfa, numer umowy. |
| **Współczynnik konwersji** | kWh/m³ | Współczynnik przeliczeniowy m³→kWh z ostatniej faktury. Przydatny do integracji licznika gazu w panelu Energii HA. Atrybuty: numer faktury, data, zużycie m³/kWh, taryfa, numer umowy. |

## Instalacja

### HACS (zalecane)

1. Otwórz HACS → **Integracje**
2. Kliknij ⋮ → **Własne repozytoria**
3. Wpisz `keysim86/myORLEN-Gas-Sensor`, kategoria: **Integracja**
4. Zainstaluj **myORLEN Gas Sensor**
5. Uruchom ponownie Home Assistant

### Ręczna

Skopiuj katalog `custom_components/myorlen_gas_sensor` do `config/custom_components/`, następnie zrestartuj Home Assistant.

## Konfiguracja

Przejdź do: **Ustawienia → Urządzenia i usługi → Dodaj integrację → myORLEN Gas Sensor**

W kreatorze podaj login i hasło do konta myORLEN oraz wybierz metodę uwierzytelniania.

### Metody uwierzytelniania

**ORLEN ID (domyślna)**
Logowanie przez SSO ORLEN ID — zalecane dla kont utworzonych lub zmigrowanych do ORLEN ID.

**eBOK Login**
Bezpośrednie logowanie przez klasyczny endpoint eBOK (`/auth/login`). Użyj tej metody jeśli Twoje konto pochodzi z portalu PGNiG/eBOK i nie zostało zmigrowane do ORLEN ID. Ta metoda **nie wymaga kodu SMS**.

### Dwustopniowe logowanie (ORLEN ID)

Od **1 września 2026** ORLEN wymaga potwierdzenia logowania kodem SMS i nie da się tego pominąć — ekran, który wcześniej miał przycisk „Pomiń", ma teraz wyłącznie „Włącz".

Jak to działa w integracji:

1. Przy pierwszym logowaniu integracja rejestruje konto w 2FA i zamawia kod SMS.
2. Home Assistant pokazuje powiadomienie **„Wymagane ponowne uwierzytelnienie"**. Otwórz je i wpisz kod z SMS-a — kod jest ważny kilka minut.
3. Po zalogowaniu integracja **zapamiętuje ciasteczka sesji** i zapisuje je we wpisie konfiguracji. Dopóki ORLEN uznaje tę sesję, kolejne logowania — również po restarcie Home Assistanta — idą bez SMS-a.

Kodu SMS nie da się obejść automatycznie: kod przychodzi na telefon i nie ma go skąd odczytać. Jeśli ORLEN unieważni sesję, integracja poprosi o kolejny kod tym samym powiadomieniem.

## Częstotliwość odświeżania

Dane są pobierane co **8 godzin** oraz przy starcie.

Gdy odświeżanie się nie powiedzie, kolejne próby są coraz rzadsze: **15 minut, 30, 60, 120…** aż do 8 godzin. Licznik zeruje się po pierwszym udanym odczycie, więc chwilowa czkawka sieci nic nie spowalnia na dłużej.

Niezależnie od tego **logowanie ma własny bezpiecznik**: po nieudanej próbie żaden sensor nie wywoła kolejnej przed końcem przerwy. Wcześniej każdy z sześciu sensorów ponawiał niezależnie co 15 minut, co przy zepsutym logowaniu dawało **24 nieudane logowania na godzinę** — a tak właśnie blokuje się konta.

## Uwaga prawna

Projekt prywatny, niepowiązany z myORLEN ani ORLEN S.A. Wszelkie nazwy produktów i znaki towarowe należą do ich właścicieli. Autor nie ponosi odpowiedzialności za dane prezentowane przez integrację.
