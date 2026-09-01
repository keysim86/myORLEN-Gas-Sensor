import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback

from .myorlen_api import myORLENApi, AUTH_METHOD_ORLEN_ID

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

DOMAIN = "myorlen_gas_sensor"

async def async_setup(hass, config):
    hass.data[DOMAIN] = {}

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


CONF_COOKIES = "cookies"


async def async_setup_entry(hass, config_entry):
    """Jedno API na wpis konfiguracji -- i to jest cala rzecz.

    Wczesniej kazda platforma robila sobie wlasny obiekt myORLENApi, wiec
    kazdy mial wlasny token i wlasny licznik niepowodzen. Bezpiecznik
    logowania nie mialby czego pilnowac. Teraz obiekt jest jeden, lezy
    w hass.data i wszystkie sensory dzieluja z nim sesje, token i przerwe
    po bledzie."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    @callback
    def _zapisz_ciasteczka(jar):
        # Ciasteczka zmieniaja sie rzadko; zapisujemy tylko realna zmiane,
        # zeby nie przepisywac wpisu konfiguracji przy kazdym logowaniu.
        if jar and jar != config_entry.data.get(CONF_COOKIES):
            hass.config_entries.async_update_entry(
                config_entry, data={**config_entry.data, CONF_COOKIES: jar}
            )

    def _z_watku_roboczego(jar):
        # Logowanie chodzi w executorze, a wpisu konfiguracji wolno dotykac
        # tylko z petli zdarzen.
        hass.add_job(_zapisz_ciasteczka, jar)

    api = myORLENApi(
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        config_entry.data.get("auth_method", AUTH_METHOD_ORLEN_ID),
        on_session_saved=_z_watku_roboczego,
    )
    # Ciasteczka z poprzedniego uruchomienia. Jesli Keycloak wystawil
    # zaufane urzadzenie, logowanie po restarcie HA pojdzie bez SMS-a.
    api.import_cookies(config_entry.data.get(CONF_COOKIES))

    @callback
    def _potrzebny_kod():
        # Idempotentne: HA nie otworzy drugiego przeplywu, gdy jeden juz wisi.
        config_entry.async_start_reauth(hass)

    api.on_sms_required = lambda: hass.add_job(_potrzebny_kod)

    hass.data[DOMAIN][config_entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])
    return True


async def async_unload_entry(hass, config_entry):
    rozladowane = await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    if rozladowane:
        hass.data.get(DOMAIN, {}).pop(config_entry.entry_id, None)
    return rozladowane
