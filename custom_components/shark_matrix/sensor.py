"""Sensor platform for Shark Matrix."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharkMatrixConfigEntry
from .api import SharkDevice
from .entity import SharkMatrixEntity


@dataclass(frozen=True, kw_only=True)
class SharkSensorDescription(SensorEntityDescription):
    """Describes a Shark sensor."""

    value_fn: Callable[[SharkDevice], int | float | str | None]


SENSORS: tuple[SharkSensorDescription, ...] = (
    SharkSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery,
    ),
    SharkSensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.error_code,
    ),
    SharkSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharkMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SharkMatrixSensor(coordinator, serial, desc)
        for serial in coordinator.data
        for desc in SENSORS
    )


class SharkMatrixSensor(SharkMatrixEntity, SensorEntity):
    """A diagnostic/state sensor for a Shark Matrix device."""

    entity_description: SharkSensorDescription

    def __init__(self, coordinator, serial: str, description: SharkSensorDescription) -> None:
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def native_value(self) -> int | float | str | None:
        return self.entity_description.value_fn(self.device)
