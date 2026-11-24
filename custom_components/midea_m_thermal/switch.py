"""Switches of a Midea M-Thermal heat pump."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MideaConfigEntry
from .entity import MideaEntity, MideaEntityDescription
from .m_thermal_modbus import Control, MideaHeatPump

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MideaSwitchEntityDescription(SwitchEntityDescription, MideaEntityDescription):
    """Describe a heat pump switch."""

    is_on_fn: Callable[[Control], bool | None]
    set_fn: Callable[[MideaHeatPump, bool], Awaitable[None]]


SWITCHES: tuple[MideaSwitchEntityDescription, ...] = (
    # Zone 1 water temperature control, the heat pump's power on this setup.
    # Only its bit of the power register is touched, so room, DHW and Zone 2
    # control keep whatever state they have.
    MideaSwitchEntityDescription(
        key="power",
        translation_key="power",
        component="control",
        is_on_fn=lambda control: control.zone1_water_power,
        set_fn=lambda device, on: device.async_set_power(on),
    ),
    MideaSwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        component="control",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda control: control.eco_mode,
        set_fn=lambda device, on: device.async_set_eco_mode(on),
    ),
    MideaSwitchEntityDescription(
        key="silent_mode",
        translation_key="silent_mode",
        component="control",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda control: control.silent_mode,
        set_fn=lambda device, on: device.async_set_silent_mode(on),
    ),
    MideaSwitchEntityDescription(
        key="climate_curve",
        translation_key="climate_curve",
        component="control",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda control: control.zone1_climate_curve,
        set_fn=lambda device, on: device.async_set_zone1_climate_curve(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the heat pump switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        MideaSwitch(coordinator, description)
        for description in SWITCHES
        if description.supported_fn(coordinator.device)
    )


class MideaSwitch(MideaEntity, SwitchEntity):
    """A bit of the heat pump's control registers."""

    entity_description: MideaSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return whether the setting is on."""
        return self.entity_description.is_on_fn(self.coordinator.device.control)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._async_write(
            self.entity_description.set_fn(self.coordinator.device, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._async_write(
            self.entity_description.set_fn(self.coordinator.device, False)
        )
