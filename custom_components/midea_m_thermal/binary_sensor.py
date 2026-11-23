"""Binary sensors of a Midea M-Thermal heat pump."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MideaConfigEntry
from .entity import MideaEntity, MideaEntityDescription
from .m_thermal_modbus import MideaHeatPump

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MideaBinarySensorEntityDescription(
    BinarySensorEntityDescription, MideaEntityDescription
):
    """Describe a heat pump binary sensor."""

    component: str = "readings"
    value_fn: Callable[[MideaHeatPump], bool | None]


def _running(
    key: str,
    value_fn: Callable[[MideaHeatPump], bool | None],
    *,
    supported_fn: Callable[[MideaHeatPump], bool] = lambda _: True,
    diagnostic: bool = False,
) -> MideaBinarySensorEntityDescription:
    """A load output of the hydraulic module: on while it runs."""
    return MideaBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        entity_registry_enabled_default=not diagnostic,
        supported_fn=supported_fn,
        value_fn=value_fn,
    )


BINARY_SENSORS: tuple[MideaBinarySensorEntityDescription, ...] = (
    _running("defrosting", lambda device: device.readings.defrosting),
    _running("anti_freeze", lambda device: device.readings.anti_freeze),
    _running("oil_return", lambda device: device.readings.oil_return, diagnostic=True),
    _running("internal_pump", lambda device: device.readings.internal_pump),
    _running("external_pump", lambda device: device.readings.external_pump),
    _running(
        "backup_heater",
        lambda device: device.readings.backup_heater_1,
        supported_fn=lambda device: bool(device.readings.backup_heater_enabled),
    ),
    _running(
        "backup_heater_2",
        lambda device: device.readings.backup_heater_2,
        supported_fn=lambda device: bool(
            device.readings.backup_heater_enabled and device.readings.three_phase
        ),
    ),
    _running(
        "tank_heater",
        lambda device: device.readings.tank_heater,
        supported_fn=lambda device: bool(device.readings.tank_heater_enabled),
    ),
    _running(
        "auxiliary_heat_source",
        lambda device: device.readings.auxiliary_heat_source,
        supported_fn=lambda device: bool(device.readings.auxiliary_heat_source_enabled),
    ),
    _running(
        "dhw_pump",
        lambda device: device.readings.dhw_pump,
        supported_fn=lambda device: device.has_function("domestic_hot_water"),
    ),
    _running(
        "mixing_pump",
        lambda device: device.readings.mixing_pump,
        supported_fn=lambda device: device.has_function("double_zone"),
    ),
    _running(
        "crankcase_heater",
        lambda device: device.readings.crankcase_heater,
        diagnostic=True,
    ),
    _running("valve_sv1", lambda device: device.readings.valve_sv1, diagnostic=True),
    _running("valve_sv2", lambda device: device.readings.valve_sv2, diagnostic=True),
    _running("valve_sv3", lambda device: device.readings.valve_sv3, diagnostic=True),
    MideaBinarySensorEntityDescription(
        key="thermostat_heating",
        translation_key="thermostat_heating",
        device_class=BinarySensorDeviceClass.HEAT,
        supported_fn=lambda device: device.has_function("room_thermostat"),
        value_fn=lambda device: device.readings.thermostat_heating,
    ),
    MideaBinarySensorEntityDescription(
        key="thermostat_cooling",
        translation_key="thermostat_cooling",
        device_class=BinarySensorDeviceClass.COLD,
        supported_fn=lambda device: device.has_function("room_thermostat"),
        value_fn=lambda device: device.readings.thermostat_cooling,
    ),
    MideaBinarySensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.readings.alarm,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors for what this heat pump has."""
    coordinator = entry.runtime_data
    async_add_entities(
        MideaBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.supported_fn(coordinator.device)
    )


class MideaBinarySensor(MideaEntity, BinarySensorEntity):
    """A status bit or load output of the heat pump."""

    entity_description: MideaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the bit the heat pump reported."""
        return self.entity_description.value_fn(self.coordinator.device)
