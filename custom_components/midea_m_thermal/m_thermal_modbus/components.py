"""Sub-systems of the Midea M-Thermal Modbus map, one Component each.

The wired controller serves three blocks. 0-22 (control) and 100-199
(operating parameters) answer bulk reads. 200-290 (configuration) refuses
them, so every register there is read on its own.
"""

from __future__ import annotations

from modbus_connection.model import (
    Component,
    NumberField,
    bit,
    bits,
    enum,
    gauge,
    integer,
    uint32,
)

from .enums import ModeSetting, OperatingState, OperationMode

# Anything that answered a zone setpoint limit outside this is not a limit.
_MAX_SETPOINT = 99

# Raw values a temperature register holds when its sensor is absent or broken:
# 0x7F and 0x7FFF are documented, 0xFF is a common unfitted-sensor marker. None
# of them is a temperature a heat pump sees. 0xFFFF is not among them: the
# registers are signed, so it is -1 °C, a reading these units report every
# winter day.
_NO_TEMPERATURE = (0x7F, 0xFF, 0x7FFF)

# A COP or EER above this is a ramp-up spike, not a reading.
_MAX_EFFICIENCY = 10


def _temperature(address: int) -> NumberField[int]:
    """A signed whole-degree temperature that is None while its sensor is absent."""
    return integer(address, nan=_NO_TEMPERATURE, unit="°C")


def _energy(address: int) -> NumberField[float]:
    """A lifetime counter in kWh over two registers, high word first.

    It reads 0 until the unit has reported it, which is no value rather than a
    reset. R290 units report hundredths of a kWh.
    """
    return uint32(address, scale=0.01, nan=0, unit="kWh")


def _efficiency(value: float | None) -> float | None:
    """A COP or EER, or None when idle or implausibly high."""
    if value is None or not 0 < value <= _MAX_EFFICIENCY:
        return None
    return value


class Control(Component):
    """Power, mode and water setpoint (holding registers 0-22)."""

    register_ranges = ((0, 22),)

    zone1_water_power = bit(0, 1, writable=True)
    """Zone 1 water temperature control. Register 0 is a bit field: bit 0 room
    control, bit 1 Zone 1 water, bit 2 DHW, bit 3 Zone 2 water."""

    mode = enum(1, ModeSetting, writable=True)
    """The mode the heat pump is told to run in."""

    zone1_target = bits(2, 0, 8, writable=True, unit="°C")
    """Zone 1 water setpoint T1s. Register 2 packs Zone 2 into its high byte,
    which a write leaves alone."""


class Readings(Component):
    """Operating parameters (holding registers 100-199), read as one block."""

    register_ranges = ((100, 199),)

    compressor_frequency = integer(100, signed=False, unit="Hz")
    operating_state = enum(101, OperatingState)

    water_inlet_temperature = _temperature(104)
    """Tw_in, the water entering the plate heat exchanger."""

    heat_exchanger_outlet_temperature = _temperature(105)
    """Tw_out, the water leaving the plate heat exchanger."""

    condenser_temperature = _temperature(106)
    """T3."""

    outdoor_temperature = _temperature(107)
    """T4, outdoor ambient."""

    discharge_temperature = _temperature(108)
    """Tp, compressor discharge."""

    suction_temperature = _temperature(109)
    """Th, compressor suction."""

    water_outlet_temperature = _temperature(110)
    """T1, total water outlet after any backup heater."""

    high_pressure = integer(116, signed=False, unit="kPa")
    low_pressure = integer(117, signed=False, unit="kPa")
    outdoor_unit_current = integer(118, signed=False, unit="A")
    outdoor_unit_voltage = integer(119, signed=False, unit="V")
    capacity = integer(123, signed=False, unit="kW")
    error_code = integer(124, signed=False)
    water_flow = gauge(138, 0.01, signed=False, unit="m³/h")

    energy_consumption = _energy(143)
    """Lifetime electrical energy, all modes."""

    energy_produced = _energy(145)
    """Lifetime heat (or cold) delivered, all modes."""

    heating_capacity = gauge(148, 0.01, signed=False, unit="kW")

    power_consumption = gauge(150, 0.01, signed=False, unit="kW")
    """Electrical power in heating mode. Reads 0 in cooling mode, even with the
    compressor running; `cooling_power_consumption` covers that."""

    _cop = gauge(151, 0.01, signed=False)

    heating_energy = _energy(158)
    """Lifetime heat delivered in heating mode."""

    heating_energy_consumption = _energy(162)
    """Lifetime electrical energy in heating mode."""

    _lifetime_cop = gauge(164, 0.01, signed=False)

    cooling_energy = _energy(165)
    """Lifetime cold delivered in cooling mode."""

    cooling_energy_consumption = _energy(169)
    """Lifetime electrical energy in cooling mode."""

    _lifetime_eer = gauge(171, 0.01, signed=False)

    cooling_capacity = gauge(180, 0.01, signed=False, unit="kW")

    cooling_power_consumption = gauge(181, 0.01, signed=False, unit="kW")
    """Electrical power in cooling mode, where `power_consumption` reads 0."""

    _eer = gauge(182, 0.01, signed=False)

    operation_mode = enum(199, OperationMode)

    @property
    def cop(self) -> float | None:
        """Heating COP, or None when idle or implausibly high.

        The register spikes to unrealistic values while the compressor ramps.
        """
        return _efficiency(self._cop)

    @property
    def eer(self) -> float | None:
        """Cooling EER, or None when idle or implausibly high."""
        return _efficiency(self._eer)

    @property
    def lifetime_cop(self) -> float | None:
        """Heat delivered over electricity used in heating mode, lifetime."""
        return _efficiency(self._lifetime_cop)

    @property
    def lifetime_eer(self) -> float | None:
        """Cold delivered over electricity used in cooling mode, lifetime."""
        return _efficiency(self._lifetime_eer)

    @property
    def outdoor_unit_power(self) -> float | None:
        """Outdoor unit power in W, from its current and voltage."""
        current = self.outdoor_unit_current
        voltage = self.outdoor_unit_voltage
        if current is None or voltage is None:
            return None
        return float(current * voltage)

    @property
    def water_temperature_delta(self) -> float | None:
        """T1 outlet minus Tw_in inlet."""
        outlet = self.water_outlet_temperature
        inlet = self.water_inlet_temperature
        if outlet is None or inlet is None:
            return None
        return float(outlet - inlet)


class SetpointLimits(Component):
    """Zone 1 water setpoint limits per mode (holding registers 201-204).

    Configuration registers answer one register per request.
    """

    max_span = 1

    cooling_max = bits(201, 0, 8, unit="°C")
    cooling_min = bits(202, 0, 8, unit="°C")
    heating_max = bits(203, 0, 8, unit="°C")
    heating_min = bits(204, 0, 8, unit="°C")

    def cooling_range(self) -> tuple[int, int] | None:
        """The cooling setpoint range, if the device reported a sane one."""
        return _sane_range(self.cooling_min, self.cooling_max)

    def heating_range(self) -> tuple[int, int] | None:
        """The heating setpoint range, if the device reported a sane one."""
        return _sane_range(self.heating_min, self.heating_max)


def _sane_range(low: int | None, high: int | None) -> tuple[int, int] | None:
    if low is None or high is None or not 0 <= low < high <= _MAX_SETPOINT:
        return None
    return low, high
