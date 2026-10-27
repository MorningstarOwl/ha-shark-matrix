"""Vacuum platform for Shark Matrix."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharkMatrixConfigEntry
from .api import SkegoxApiError
from .const import (
    OP_PAUSE,
    OP_RETURN,
    OP_START,
    POWER_MODES,
    POWER_MODES_REVERSE,
)
from .entity import SharkMatrixEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.STATE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharkMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up vacuum entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        SharkMatrixVacuum(coordinator, serial) for serial in coordinator.data
    )


class SharkMatrixVacuum(SharkMatrixEntity, StateVacuumEntity):
    """A Shark Matrix robot vacuum."""

    _attr_name = None  # use the device name
    _attr_supported_features = SUPPORT
    _attr_fan_speed_list = list(POWER_MODES)

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = serial

    @property
    def activity(self) -> VacuumActivity:
        dev = self.device
        if dev.error_code:
            return VacuumActivity.ERROR
        mode = dev.operating_mode
        if mode == OP_START:
            return VacuumActivity.CLEANING
        if mode == OP_PAUSE:
            return VacuumActivity.PAUSED
        if mode == OP_RETURN and not dev.docked:
            return VacuumActivity.RETURNING
        if dev.docked or dev.charging:
            return VacuumActivity.DOCKED
        return VacuumActivity.IDLE

    @property
    def battery_level(self) -> int | None:
        return self.device.battery

    @property
    def fan_speed(self) -> str | None:
        return POWER_MODES_REVERSE.get(self.device.power_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = self.device
        return {
            "operating_mode": dev.operating_mode,
            "error_code": dev.error_code,
            "charging": dev.charging,
            "docked": dev.docked,
            "rooms": dev.rooms,
            "rssi": dev.rssi,
        }

    async def _command(self, coro) -> None:
        try:
            await coro
        except SkegoxApiError as err:
            _LOGGER.error("Command failed for %s: %s", self._serial, err)
            raise
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        await self._command(self.coordinator.client.async_start(self._serial))

    async def async_pause(self) -> None:
        await self._command(self.coordinator.client.async_pause(self._serial))

    async def async_stop(self, **kwargs: Any) -> None:
        await self._command(self.coordinator.client.async_stop(self._serial))

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self._command(self.coordinator.client.async_return_to_base(self._serial))

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        if fan_speed not in POWER_MODES:
            _LOGGER.error("Unknown fan speed %s", fan_speed)
            return
        await self._command(
            self.coordinator.client.async_set_power_mode(
                self._serial, POWER_MODES[fan_speed]
            )
        )
