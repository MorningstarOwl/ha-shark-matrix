"""The Shark Matrix (SharkNinja AWS / skegox) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SkegoxApiError, SkegoxAuth, SkegoxAuthError, SkegoxClient
from .const import CONF_HOUSEHOLD_ID, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import SharkMatrixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.VACUUM, Platform.SENSOR]

type SharkMatrixConfigEntry = ConfigEntry[SharkMatrixCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SharkMatrixConfigEntry) -> bool:
    """Set up Shark Matrix from a config entry."""
    session = async_get_clientsession(hass)
    auth = SkegoxAuth(session, refresh_token=entry.data[CONF_REFRESH_TOKEN])
    client = SkegoxClient(session, auth, entry.data[CONF_HOUSEHOLD_ID])

    try:
        devices = await client.async_list_devices()
    except SkegoxAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SkegoxApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if not devices:
        raise ConfigEntryNotReady("no devices returned for this household")

    serials = [d.serial for d in devices if d.serial]
    coordinator = SharkMatrixCoordinator(hass, entry, client, serials)
    await coordinator.async_config_entry_first_refresh()

    # Persist a rotated refresh token so we don't lose access after restart.
    if auth.refresh_token and auth.refresh_token != entry.data[CONF_REFRESH_TOKEN]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: auth.refresh_token}
        )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SharkMatrixConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
