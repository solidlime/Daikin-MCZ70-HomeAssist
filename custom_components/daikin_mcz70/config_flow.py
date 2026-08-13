"""Config flow for the Daikin MCZ70 integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_APW,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_CODE,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_REDIRECT_URI,
    CONF_REFRESH_TOKEN,
    CONF_SPW,
    CONF_TERMINAL_ID,
    CONF_UUID,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_REDIRECT_URI,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CLOUD_FIELDS = (
    CONF_CODE,
    CONF_CLIENT_ID,
    CONF_UUID,
    CONF_CLIENT_SECRET,
    CONF_REFRESH_TOKEN,
    CONF_TERMINAL_ID,
    CONF_PORT,
    CONF_ID,
    CONF_SPW,
    CONF_APW,
    CONF_REDIRECT_URI,
)


def _schema(defaults: dict | None = None) -> vol.Schema:
    """Build the form schema. All cloud fields are optional (writes need them).

    Client ID / secret / redirect URI fall back to the APK-embedded public
    defaults for new setups, while values already saved in an entry are kept
    untouched (defaults only apply when the key is absent).
    """
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_IP_ADDRESS, default=d.get(CONF_IP_ADDRESS, "")): str,
            vol.Optional(CONF_CODE, default=d.get(CONF_CODE, "")): str,
            vol.Optional(CONF_CLIENT_ID, default=d.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID)): str,
            vol.Optional(CONF_UUID, default=d.get(CONF_UUID, "")): str,
            vol.Optional(CONF_CLIENT_SECRET, default=d.get(CONF_CLIENT_SECRET, DEFAULT_CLIENT_SECRET)): str,
            vol.Optional(CONF_REFRESH_TOKEN, default=d.get(CONF_REFRESH_TOKEN, "")): str,
            vol.Optional(CONF_TERMINAL_ID, default=d.get(CONF_TERMINAL_ID, "")): str,
            vol.Optional(CONF_PORT, default=d.get(CONF_PORT, "")): str,
            vol.Optional(CONF_ID, default=d.get(CONF_ID, "")): str,
            vol.Optional(CONF_SPW, default=d.get(CONF_SPW, "")): str,
            vol.Optional(CONF_APW, default=d.get(CONF_APW, "")): str,
            vol.Optional(CONF_REDIRECT_URI, default=d.get(CONF_REDIRECT_URI, DEFAULT_REDIRECT_URI)): str,
        }
    )


class DaikinMcZ70ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_schema())

        for entry in self._async_current_entries():
            if entry.data.get(CONF_IP_ADDRESS) == user_input[CONF_IP_ADDRESS]:
                return self.async_abort(reason="already_configured")

        from . import LocalAPI

        api = LocalAPI(user_input[CONF_IP_ADDRESS], async_get_clientsession(self.hass))
        info = await api.get_basic_info()
        if not info:
            return self.async_show_form(
                step_id="user", data_schema=_schema(user_input), errors={"base": "cannot_connect"}
            )

        mac = info.get("mac")
        if mac:
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()

        self._data = user_input
        self._title = info.get("name") or "Daikin MCZ70"

        if await self._test_cloud(user_input):
            return self.async_create_entry(title=self._title, data=user_input)
        return await self.async_step_cloud_warning()

    async def _test_cloud(self, data: dict) -> bool:
        """Try the cloud credentials: refresh with a supplied refresh token,
        otherwise login with the authorization code. Missing credentials are
        not an error here (local-only setup is allowed with a warning)."""
        from . import CloudAPI

        cloud = CloudAPI(self.hass, None, async_get_clientsession(self.hass), data)
        try:
            if data.get(CONF_REFRESH_TOKEN):
                await cloud._refresh()
            elif all(data.get(field) for field in (CONF_CODE, CONF_CLIENT_ID, CONF_UUID, CONF_CLIENT_SECRET)):
                await cloud.login()
            else:
                return False
        except Exception as err:
            _LOGGER.warning("Cloud credential test failed: %s", err)
            return False
        return True

    async def async_step_cloud_warning(self, user_input=None):
        """Confirm setup even though cloud login failed (writes will not work)."""
        if user_input is not None:
            return self.async_create_entry(title=self._title, data=self._data)
        return self.async_show_form(step_id="cloud_warning", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Re-enter local/cloud settings. Applied on the next HA start.

    A config entry update listener is intentionally not registered: token
    persistence also updates entry data, and reloading on every token save
    would restart the integration repeatedly.
    """

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            data = {**self._entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._entry, data=data)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=_schema(dict(self._entry.data)))
