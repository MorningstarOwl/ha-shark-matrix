"""DataUpdateCoordinator for Shark Matrix."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SharkDevice, SkegoxApiError, SkegoxAuthError, SkegoxClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SharkMatrixCoordinator(DataUpdateCoordinator[dict[str, SharkDevice]]):
    """Polls the skegox API and keeps a {serial: SharkDevice} map."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SkegoxClient,
        serials: list[str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self._serials = serials

    async def _async_update_data(self) -> dict[str, SharkDevice]:
        result: dict[str, SharkDevice] = {}
        try:
            for serial in self._serials:
                result[serial] = await self.client.async_get_device(serial)
        except SkegoxAuthError as err:
            # trigger reauth
            raise UpdateFailed(f"auth error: {err}") from err
        except SkegoxApiError as err:
            raise UpdateFailed(f"api error: {err}") from err
        return result
