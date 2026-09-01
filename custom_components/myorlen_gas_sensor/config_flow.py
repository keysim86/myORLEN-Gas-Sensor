import logging
from typing import Optional, Dict, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import selector

from .myorlen_api import (myORLENApi, AUTH_METHOD_ORLEN_ID, AUTH_METHOD_EBOK,
                          SmsCodeRequired)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "myorlen_gas_sensor"

SMS_SCHEMA = vol.Schema({vol.Required("sms_code"): cv.string})


AUTH_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required("auth_method", default=AUTH_METHOD_ORLEN_ID): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[AUTH_METHOD_ORLEN_ID, AUTH_METHOD_EBOK],
            mode=selector.SelectSelectorMode.LIST,
            translation_key="auth_method",
        )
    ),
})


class myORLENGasConfigFlow(ConfigFlow, domain="myorlen_gas_sensor"):
    """Example config flow."""

    async def async_step_import(self, import_config):
        return self.async_abort(reason="one_instance_at_a_time_please")

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            api = myORLENApi(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input["auth_method"])
            try:
                token = await self.hass.async_add_executor_job(api.login)
                if not token:
                    raise Exception("Login failed")
                return self.async_create_entry(title="myORLEN sensor", data=user_input)
            except Exception as e:
                errors = {"base": "verify_connection_failed"}
        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    # ------------------------------------------------------------------
    #  KOD SMS PO WYMUSZENIU 2FA PRZEZ ORLEN (2026-09-01)
    # ------------------------------------------------------------------
    #
    # Logowanie nie moze zapytac o kod samo z siebie: chodzi w tle, w watku
    # roboczym, bez zadnego okna. Dlatego API zatrzymuje sie na formularzu
    # z kodem, zapamietuje sesje i prosi HA o ponowne uwierzytelnienie --
    # a caly dialog z czlowiekiem dzieje sie tutaj.
    #
    # SESJA MUSI PRZETRWAC te przerwe, i to jest sedno calej konstrukcji.
    # Keycloak wiaze kod SMS z konkretna sesja i konkretnym formularzem, wiec
    # nie wystarczy zapamietac kodu -- trzeba dokonczyc TO SAMO logowanie.
    # Obiekt API lezy w hass.data i zyje miedzy przeplywami, wiec sesja czeka
    # razem z nim.

    async def async_step_reauth(self, entry_data):
        self._wpis = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_sms()

    async def async_step_sms(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        api = self.hass.data.get(DOMAIN, {}).get(self._wpis.entry_id)
        if api is None:
            return self.async_abort(reason="integration_not_loaded")

        # Wejscie z menu, a nie po nieudanym logowaniu: nic nie czeka na kod,
        # wiec trzeba go najpierw zamowic. Przerwe karna kasujemy, bo to
        # czlowiek prosi o logowanie, a nie maszyna pukajaca w kolko.
        if user_input is None and not api.waiting_for_sms():
            api.reset_backoff()
            try:
                await self.hass.async_add_executor_job(api.login)
            except SmsCodeRequired:
                pass
            except Exception as e:
                _LOGGER.error("Nie udalo sie zamowic kodu SMS: %s", e)
                errors = {"base": "sms_request_failed"}

        if user_input is not None:
            try:
                token = await self.hass.async_add_executor_job(
                    api.submit_sms_code, user_input["sms_code"])
                if not token:
                    raise Exception("ORLEN nie oddal tokenu mimo przyjecia kodu")
            except Exception as e:
                _LOGGER.warning("Kod SMS odrzucony: %s", e)
                errors = {"base": "sms_code_invalid"}
            else:
                # Ciasteczka sa juz zapisane przez API; przeladowanie wpisu
                # stawia sensory od nowa, tym razem z waznym tokenem.
                await self.hass.config_entries.async_reload(self._wpis.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="sms", data_schema=SMS_SCHEMA, errors=errors,
            description_placeholders={"login": self._wpis.data.get(CONF_USERNAME, "")},
        )
