"""The Midea M-Thermal heat pump integration."""

from __future__ import annotations

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID
from .coordinator import MideaConfigEntry, MideaDataUpdateCoordinator
from .m_thermal_modbus import MideaHeatPump

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: MideaConfigEntry) -> bool:
    """Set up the heat pump from a config entry.

    The connection belongs to the modbus integration, which shares it with any
    other integration on the same gateway and closes it once the last entry
    holding a unit on it unloads.
    """
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )
    device = MideaHeatPump(unit)
    # The device asked the shared link for its timeout; withdraw it on unload so
    # it does not outlive the entry while another integration keeps the link.
    entry.async_on_unload(lambda: unit.require_timeout(None))
    coordinator = MideaDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MideaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
