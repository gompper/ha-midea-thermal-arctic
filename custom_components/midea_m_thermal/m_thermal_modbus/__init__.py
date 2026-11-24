"""Device library for Midea M-Thermal heat pumps over Modbus.

Built on modbus-connection and free of Home Assistant imports, so it can move
to its own PyPI package unchanged.
"""

from .components import CLIMATE_CURVES, Control, Functions, Readings, SetpointLimits
from .device import (
    DEFAULT_COOLING_RANGE,
    DEFAULT_HEATING_RANGE,
    REQUEST_TIMEOUT,
    MideaHeatPump,
    UpdateReport,
)
from .enums import (
    ERROR_CODES,
    ModeSetting,
    OperatingState,
    OperationMode,
    SilentLevel,
    SubModel,
)

__all__ = [
    "CLIMATE_CURVES",
    "DEFAULT_COOLING_RANGE",
    "DEFAULT_HEATING_RANGE",
    "ERROR_CODES",
    "REQUEST_TIMEOUT",
    "Control",
    "Functions",
    "MideaHeatPump",
    "ModeSetting",
    "OperatingState",
    "OperationMode",
    "Readings",
    "SetpointLimits",
    "SilentLevel",
    "SubModel",
    "UpdateReport",
]
