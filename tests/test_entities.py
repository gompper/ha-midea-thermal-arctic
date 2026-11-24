"""Tests for the Midea M-Thermal entities."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    IllegalDataValueError,
    ModbusConnectionError,
)
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .conftest import SNAPSHOT_4KW, as_raw

SCAN = timedelta(seconds=30)
TARGET = "number.heat_pump_target_temperature"
MODE = "select.heat_pump_mode"
POWER = "switch.heat_pump_power"
ENERGY = "sensor.heat_pump_energy_consumption"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "state", "unit"),
    [
        ("sensor.heat_pump_operating_state", "heating", None),
        ("sensor.heat_pump_operation_mode", "heating", None),
        ("sensor.heat_pump_outdoor_temperature", "4", "°C"),
        ("sensor.heat_pump_water_inlet_temperature", "28", "°C"),
        ("sensor.heat_pump_water_outlet_temperature", "32", "°C"),
        ("sensor.heat_pump_heat_exchanger_outlet_temperature", "32", "°C"),
        ("sensor.heat_pump_discharge_temperature", "52", "°C"),
        ("sensor.heat_pump_suction_temperature", "3", "°C"),
        ("sensor.heat_pump_condenser_temperature", "-1", "°C"),
        ("sensor.heat_pump_water_temperature_delta", "4.0", "°C"),
        ("sensor.heat_pump_water_flow", "1.07", "m³/h"),
        ("sensor.heat_pump_compressor_frequency", "29", "Hz"),
        ("sensor.heat_pump_high_pressure", "1350", "kPa"),
        ("sensor.heat_pump_low_pressure", "430", "kPa"),
        ("sensor.heat_pump_power_consumption", "0.87", "kW"),
        ("sensor.heat_pump_heating_capacity", "3.49", "kW"),
        ("sensor.heat_pump_cop", "4.01", None),
        ("sensor.heat_pump_cooling_power_consumption", "0.0", "kW"),
        ("sensor.heat_pump_cooling_capacity", "0.0", "kW"),
        ("sensor.heat_pump_eer", STATE_UNKNOWN, None),
        ("sensor.heat_pump_outdoor_unit_current", "3", "A"),
        ("sensor.heat_pump_outdoor_unit_voltage", "223", "V"),
        ("sensor.heat_pump_outdoor_unit_power", "669.0", "W"),
        ("sensor.heat_pump_energy_consumption", "317.18", "kWh"),
        ("sensor.heat_pump_energy_produced", "1150.07", "kWh"),
        ("sensor.heat_pump_heating_energy_consumption", "317.14", "kWh"),
        ("sensor.heat_pump_heating_energy_produced", "1149.92", "kWh"),
        ("sensor.heat_pump_lifetime_cop", "3.62", None),
        ("sensor.heat_pump_cooling_energy_consumption", STATE_UNKNOWN, "kWh"),
        ("sensor.heat_pump_cooling_energy_produced", STATE_UNKNOWN, "kWh"),
        ("sensor.heat_pump_lifetime_eer", STATE_UNKNOWN, None),
        ("sensor.heat_pump_error_code", "0", None),
        ("sensor.heat_pump_error", "none", None),
        ("sensor.heat_pump_climate_curve_target_temperature", STATE_UNKNOWN, "°C"),
        ("sensor.heat_pump_ambient_heat", "2.89", "kW"),
        ("sensor.heat_pump_ambient_heat_energy", "995.5", "kWh"),
        ("sensor.heat_pump_fan_speed", "450", "rpm"),
        ("sensor.heat_pump_compressor_operating_time", "338", "h"),
        ("sensor.heat_pump_circulation_pump_duty_cycle", "15.0", "%"),
        ("binary_sensor.heat_pump_defrosting", "off", None),
        ("binary_sensor.heat_pump_frost_protection", "off", None),
        ("binary_sensor.heat_pump_circulation_pump", "on", None),
        ("binary_sensor.heat_pump_external_circulation_pump", "on", None),
        ("binary_sensor.heat_pump_alarm", "off", None),
        (POWER, "on", None),
        ("switch.heat_pump_eco_mode", "off", None),
        ("switch.heat_pump_silent_mode", "on", None),
        ("switch.heat_pump_climate_curve", "off", None),
        ("select.heat_pump_silent_mode_level", "level_2", None),
        ("select.heat_pump_climate_curve_number", "3", None),
        (MODE, "heating", None),
        (TARGET, "28", "°C"),
    ],
)
async def test_entity_states(
    hass: HomeAssistant, entity_id: str, state: str, unit: str | None
) -> None:
    """Entities show the heat pump's register dump."""
    entity = hass.states.get(entity_id)
    assert entity is not None, entity_id
    assert entity.state == state
    assert entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit


@pytest.mark.usefixtures("init_integration")
async def test_target_range_follows_the_mode(
    hass: HomeAssistant, mock_unit: MockModbusUnit, freezer: FrozenDateTimeFactory
) -> None:
    """The setpoint bounds move with the mode, from the device's own limits."""
    state = hass.states.get(TARGET)
    assert (state.attributes[ATTR_MIN], state.attributes[ATTR_MAX]) == (25, 55)

    mock_unit.holding[1] = 2  # cooling, set on the wired controller
    mock_unit.holding[2] = 0x1E14  # 20 °C
    await _poll(hass, freezer)

    state = hass.states.get(TARGET)
    assert state.state == "20"
    assert (state.attributes[ATTR_MIN], state.attributes[ATTR_MAX]) == (5, 25)


@pytest.mark.usefixtures("init_integration")
async def test_set_target(hass: HomeAssistant, mock_unit: MockModbusUnit) -> None:
    """Setting the target writes Zone 1 and keeps Zone 2."""
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TARGET, ATTR_VALUE: 42},
        blocking=True,
    )
    assert mock_unit.holding[2] == 0x1E2A
    assert hass.states.get(TARGET).state == "42"


@pytest.mark.usefixtures("init_integration")
async def test_set_target_out_of_range_is_refused(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Home Assistant refuses a setpoint the mode does not allow."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: TARGET, ATTR_VALUE: 20},
            blocking=True,
        )
    assert mock_unit.holding[2] == 7708


@pytest.mark.usefixtures("init_integration")
async def test_select_cooling_moves_the_setpoint(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Switching to cooling pulls a heating setpoint down to the cooling max."""
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TARGET, ATTR_VALUE: 40},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: MODE, ATTR_OPTION: "cooling"},
        blocking=True,
    )
    assert mock_unit.holding[1] == 2
    assert mock_unit.holding[2] == 0x1E19

    await hass.async_block_till_done()
    assert hass.states.get(MODE).state == "cooling"
    state = hass.states.get(TARGET)
    assert state.state == "25"
    assert state.attributes[ATTR_MAX] == 25


@pytest.mark.usefixtures("init_integration")
async def test_power_switch(hass: HomeAssistant, mock_unit: MockModbusUnit) -> None:
    """The switch flips Zone 1 water control and nothing else."""
    mock_unit.holding[0] = 0b1010
    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: POWER}, blocking=True
    )
    assert mock_unit.holding[0] == 0b1000
    assert hass.states.get(POWER).state == "off"

    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: POWER}, blocking=True
    )
    assert mock_unit.holding[0] == 0b1010
    assert hass.states.get(POWER).state == "on"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "bit"),
    [
        ("switch.heat_pump_silent_mode", 6),
        ("switch.heat_pump_eco_mode", 10),
        ("switch.heat_pump_climate_curve", 12),
    ],
)
async def test_function_switches_touch_only_their_bit(
    hass: HomeAssistant, mock_unit: MockModbusUnit, entity_id: str, bit: int
) -> None:
    """Leak detection, the disinfection timer and the rest keep their state."""
    others = 0b1001_0000_1001_0001 & ~(1 << bit)
    mock_unit.holding[5] = others
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert mock_unit.holding[5] == others | 1 << bit
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert mock_unit.holding[5] == others
    assert hass.states.get(entity_id).state == "off"


@pytest.mark.usefixtures("init_integration")
async def test_silent_level_select(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """The level is bit 7 of the function register; the rest stays."""
    entity_id = "select.heat_pump_silent_mode_level"
    assert hass.states.get(entity_id).attributes["options"] == ["level_1", "level_2"]
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "level_1"},
        blocking=True,
    )
    assert mock_unit.holding[5] == 0b0100_0000
    assert mock_unit.holding[20] == 0
    assert hass.states.get(entity_id).state == "level_1"


@pytest.mark.usefixtures("init_integration")
async def test_climate_curve_select(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Curves 1-9 are offered and written to register 18."""
    entity_id = "select.heat_pump_climate_curve_number"
    assert hass.states.get(entity_id).attributes["options"] == [
        str(curve) for curve in range(1, 10)
    ]
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "7"},
        blocking=True,
    )
    assert mock_unit.holding[18] == 7
    assert hass.states.get(entity_id).state == "7"


@pytest.mark.usefixtures("init_integration")
async def test_climate_curve_out_of_range_is_unknown(
    hass: HomeAssistant, mock_unit: MockModbusUnit, freezer: FrozenDateTimeFactory
) -> None:
    """A curve number the controller should not report shows as unknown."""
    mock_unit.holding[18] = 0
    await _poll(hass, freezer)
    assert hass.states.get("select.heat_pump_climate_curve_number").state == (
        STATE_UNKNOWN
    )


@pytest.mark.usefixtures("init_integration")
async def test_refused_write_raises(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """A write the heat pump rejects reaches the user as an error."""
    mock_unit.fail_write(1, IllegalDataValueError())
    with pytest.raises(HomeAssistantError, match="did not accept the change"):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: MODE, ATTR_OPTION: "auto"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_cop_is_unknown_while_idle(
    hass: HomeAssistant, mock_unit: MockModbusUnit, freezer: FrozenDateTimeFactory
) -> None:
    """COP reads 0 while the compressor is off, which is no value."""
    mock_unit.holding[151] = 0
    await _poll(hass, freezer)
    assert hass.states.get("sensor.heat_pump_cop").state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_cooling_readings(
    hass: HomeAssistant, mock_unit: MockModbusUnit, freezer: FrozenDateTimeFactory
) -> None:
    """Cooling reports through its own registers, and its counters start."""
    mock_unit.holding.update(
        {150: 0, 180: 412, 181: 103, 182: 400, 166: 2550, 170: 610, 171: 418}
    )
    await _poll(hass, freezer)
    expected = {
        "power_consumption": "0.0",
        "cooling_capacity": "4.12",
        "cooling_power_consumption": "1.03",
        "eer": "4.0",
        "cooling_energy_produced": "25.5",
        "cooling_energy_consumption": "6.1",
        "lifetime_eer": "4.18",
    }
    for key, state in expected.items():
        assert hass.states.get(f"sensor.heat_pump_{key}").state == state, key


@pytest.mark.usefixtures("init_integration")
async def test_energy_holds_through_outages_and_glitches(
    hass: HomeAssistant, mock_unit: MockModbusUnit, freezer: FrozenDateTimeFactory
) -> None:
    """The lifetime counter never gaps or dips, so statistics stay intact."""
    mock_unit.fail_requests(ModbusConnectionError("gone"))
    await _poll(hass, freezer)
    assert hass.states.get(ENERGY).state == "317.18"

    mock_unit.fail_requests(None)
    mock_unit.holding[144] = 0  # counter not reported
    await _poll(hass, freezer)
    assert hass.states.get(ENERGY).state == "317.18"

    mock_unit.holding[144] = 31700  # a rounding glitch just below the last value
    await _poll(hass, freezer)
    assert hass.states.get(ENERGY).state == "317.18"

    mock_unit.holding[144] = 31800
    await _poll(hass, freezer)
    assert hass.states.get(ENERGY).state == "318.0"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "entity_id",
    [
        # The 10 kW unit has no backup heater, no room sensor and no thermostat.
        "binary_sensor.heat_pump_backup_heater",
        "binary_sensor.heat_pump_backup_heater_stage_2",
        "binary_sensor.heat_pump_tank_heater",
        "binary_sensor.heat_pump_auxiliary_heat_source",
        "binary_sensor.heat_pump_hot_water_circulation_pump",
        "binary_sensor.heat_pump_zone_2_mixing_pump",
        "binary_sensor.heat_pump_room_thermostat_heating_demand",
        "sensor.heat_pump_room_temperature",
        # Detail readings start disabled.
        "sensor.heat_pump_refrigerant_liquid_temperature",
        "sensor.heat_pump_dc_bus_voltage",
        "binary_sensor.heat_pump_3_way_valve_sv1",
    ],
)
async def test_entities_left_out(hass: HomeAssistant, entity_id: str) -> None:
    """Entities for what the unit lacks are not created; details start off."""
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("raw", "state"), [(0, "none"), (9, "e8"), (31, "pb"), (200, "unknown")]
)
async def test_error_shows_the_controller_code(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    raw: int,
    state: str,
) -> None:
    """Register 124 maps to the code the wired controller displays."""
    mock_unit.holding[124] = raw
    await _poll(hass, freezer)
    assert hass.states.get("sensor.heat_pump_error").state == state


async def test_mode_offers_only_heating_without_cooling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """With cooling disabled by the installer, cooling and auto are not offered."""
    mock_unit.holding[210] &= ~(1 << 9)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(MODE).attributes["options"] == ["heating"]


async def test_mode_keeps_all_options_when_functions_are_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """A controller that hides its function settings keeps every mode."""
    mock_unit.fail_read(210, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(MODE).attributes["options"] == [
        "auto",
        "cooling",
        "heating",
    ]


async def test_entities_follow_the_4kw_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """The 4 kW read: backup heater shown, heating only, model named."""
    mock_unit.load_raw(as_raw(SNAPSHOT_4KW))
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.heat_pump_backup_heater").state == "off"
    assert hass.states.get("binary_sensor.heat_pump_backup_heater_stage_2") is None
    assert hass.states.get(MODE).attributes["options"] == ["heating"]
    assert (
        hass.states.get("sensor.heat_pump_climate_curve_target_temperature").state
        == "32"
    )
    [device] = dr.async_entries_for_config_entry(
        dr.async_get(hass), mock_config_entry.entry_id
    )
    assert device.model == "M-Thermal R290-A 4 kW"
    assert device.sw_version == "24"


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Diagnostics carry the raw registers and redact the gateway address."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics["entry"]["host"] == "**REDACTED**"
    assert diagnostics["updated"] == ["control", "readings"]
    assert diagnostics["failed"] == {}
    assert diagnostics["registers"]["holding"]["2"] == 7708
    assert diagnostics["registers"]["holding"]["144"] == 31718
