"""The Midea M-Thermal heat pump, reached through a ModbusUnit."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING

from modbus_connection import ModbusExceptionError
from modbus_connection.model import Device, Raw, UpdateReport

from .components import Control, Readings, SetpointLimits
from .enums import ModeSetting

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

# Sub-systems read on every poll, by attribute name.
POLLED = ("control", "readings")

# Every sub-system, for the raw register map.
ALL_COMPONENTS = ("control", "readings", "limits")

# Zone 1 setpoint ranges from the Midea documentation, used until the device
# reports its own.
DEFAULT_COOLING_RANGE = (5, 25)
DEFAULT_HEATING_RANGE = (25, 55)

REQUEST_TIMEOUT = 3.0
"""Seconds to wait for an answer. The largest read, the 100-register operating
block, takes about 0.3 s at 9600 baud; the link's 10 s default only delays
noticing a gateway whose RS-485 side has gone quiet."""

__all__ = [
    "ALL_COMPONENTS",
    "DEFAULT_COOLING_RANGE",
    "DEFAULT_HEATING_RANGE",
    "POLLED",
    "REQUEST_TIMEOUT",
    "MideaHeatPump",
    "UpdateReport",
]


class MideaHeatPump(Device):
    """A Midea M-Thermal heat pump on a Modbus unit.

    The unit is shared and owned by the caller; this object only reads and
    writes registers through it, and asks the link for `REQUEST_TIMEOUT`.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        """Model the heat pump behind a unit."""
        super().__init__(unit)
        unit.require_timeout(REQUEST_TIMEOUT)
        self.control = Control(unit)
        self.readings = Readings(unit)
        self.limits = SetpointLimits(unit)

    async def _async_setup(self) -> None:
        """Read the setpoint limits once; they only change in the installer menu.

        A controller that refuses them keeps the documented defaults for good.
        Any other error propagates, failing this poll, and the next poll tries
        again.
        """
        try:
            await self.limits.async_update(notify=False)
        except ModbusExceptionError as err:
            _LOGGER.warning(
                "The heat pump refused its setpoint limits, using the defaults: %s",
                err,
            )

    async def async_update(self) -> UpdateReport:
        """Refresh every polled sub-system, each on its own.

        A sub-system the device rejects lands in the report and the rest still
        refresh. A dropped link raises at once, and so does a timeout before
        anything answered, since that means nothing is listening.
        """
        return await self.async_poll(POLLED)

    async def async_read_raw(self, names: Iterable[str] = ALL_COMPONENTS) -> Raw:
        """Every register this device reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)

    def target_range(self, mode: ModeSetting | None = None) -> tuple[int, int]:
        """The Zone 1 setpoint range for a mode, the current mode by default.

        Auto follows the heating range.
        """
        if mode is None:
            mode = self.control.mode
        if mode is ModeSetting.COOLING:
            return self.limits.cooling_range() or DEFAULT_COOLING_RANGE
        return self.limits.heating_range() or DEFAULT_HEATING_RANGE

    async def async_set_power(self, on: bool) -> None:
        """Switch Zone 1 water temperature control, keeping the other bits."""
        await self.control.write("zone1_water_power", on)

    async def async_set_zone1_target(self, value: int) -> int:
        """Write the Zone 1 setpoint, clamped into the live mode's range.

        The mode is read fresh, so a mode changed on the wired controller since
        the last poll is honoured. Returns the value written.
        """
        await self.control.async_update(notify=False)
        low, high = self.target_range()
        target = max(low, min(int(value), high))
        await self.control.write("zone1_target", target)
        return target

    async def async_set_mode(self, mode: ModeSetting) -> None:
        """Switch mode, then pull the setpoint into the new mode's range.

        Both modes share one setpoint register, so a heating setpoint of 35 °C
        is out of range once the heat pump is cooling.
        """
        await self.control.write("mode", mode)
        await self.control.async_update(notify=False)
        target = self.control.zone1_target
        low, high = self.target_range(mode)
        if target is not None and not low <= target <= high:
            await self.control.write("zone1_target", max(low, min(target, high)))
