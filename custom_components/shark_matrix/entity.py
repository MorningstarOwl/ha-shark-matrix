"""Base entity for Shark Matrix."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SharkDevice
from .const import DOMAIN
from .coordinator import SharkMatrixCoordinator


class SharkMatrixEntity(CoordinatorEntity[SharkMatrixCoordinator]):
    """Common base: ties an entity to one device (by serial)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SharkMatrixCoordinator, serial: str) -> None:
        super().__init__(coordinator)
        self._serial = serial

    @property
    def device(self) -> SharkDevice:
        return self.coordinator.data[self._serial]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._serial in self.coordinator.data
            and self.device.online
        )

    @property
    def device_info(self) -> DeviceInfo:
        dev = self.coordinator.data.get(self._serial)
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            manufacturer="Shark (SharkNinja)",
            name=dev.name if dev else self._serial,
            model=dev.model if dev else None,
            sw_version=dev.firmware if dev else None,
            connections={("mac", dev.mac)} if dev and dev.mac else set(),
            serial_number=self._serial,
        )
