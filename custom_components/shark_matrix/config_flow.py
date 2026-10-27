"""Config flow for Shark Matrix."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SkegoxApiError, SkegoxAuth, SkegoxAuthError, SkegoxClient
from .const import CONF_HOUSEHOLD_ID, CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Required(CONF_HOUSEHOLD_ID): str,
    }
)


class SharkMatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark Matrix."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> tuple[str, str] | None:
        """Return (user_id, device_summary) on success, else raise."""
        session = async_get_clientsession(self.hass)
        auth = SkegoxAuth(session, refresh_token=data[CONF_REFRESH_TOKEN])
        client = SkegoxClient(session, auth, data[CONF_HOUSEHOLD_ID])
        user_id = await auth.async_user_id()
        devices = await client.async_list_devices()
        if not devices:
            raise NoDevices
        # keep any rotated refresh token
        if auth.refresh_token:
            data[CONF_REFRESH_TOKEN] = auth.refresh_token
        names = ", ".join(d.name for d in devices)
        return user_id, names

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_id, names = await self._validate(user_input)
            except SkegoxAuthError:
                errors["base"] = "invalid_auth"
            except NoDevices:
                errors["base"] = "no_devices"
            except SkegoxApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Shark Matrix")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Shark Matrix ({names})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class NoDevices(Exception):
    """No devices found for the household."""
