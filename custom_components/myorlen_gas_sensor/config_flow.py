from typing import Optional, Dict, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import selector

from .myorlen_api import myORLENApi, AUTH_METHOD_ORLEN_ID, AUTH_METHOD_EBOK


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
