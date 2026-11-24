"""Register value enumerations of the Midea M-Thermal Modbus map."""

from enum import IntEnum


class ModeSetting(IntEnum):
    """The mode the heat pump is told to run in (register 1)."""

    AUTO = 1
    COOLING = 2
    HEATING = 3


class SilentLevel(IntEnum):
    """How quiet silent mode runs (register 5 bit 7)."""

    LEVEL_1 = 0
    LEVEL_2 = 1


class OperatingState(IntEnum):
    """What the heat pump is doing right now (register 101)."""

    IDLE = 0
    COOLING = 2
    HEATING = 3


class OperationMode(IntEnum):
    """The heat pump operation mode (register 199)."""

    OFF = 0
    COOLING = 2
    HEATING = 3
    DHW = 5


class SubModel(IntEnum):
    """The hydraulic module sub-model (register 190)."""

    R32_P = 0
    AQUA = 1
    C_R32_P = 2
    R290_A = 3
    R290_N = 4
    C_R290_A = 5
    C_R290_N = 6
    R32_A = 7
    C_R32_A = 8
    R290_M = 9
    R32_H = 10

    @property
    def label(self) -> str:
        """The name Midea prints, such as R290-A."""
        return {SubModel.AQUA: "Aqua"}.get(self, self.name.replace("_", "-"))


# Codes of the current error (register 124), from Midea's error code table 1.
ERROR_CODES: dict[int, str] = {
    1: "E0",
    2: "E1",
    3: "E2",
    4: "E3",
    5: "E4",
    6: "E5",
    7: "E6",
    8: "E7",
    9: "E8",
    10: "E9",
    11: "EA",
    12: "Eb",
    13: "Ec",
    14: "Ed",
    15: "EE",
    20: "P0",
    21: "P1",
    23: "P3",
    24: "P4",
    25: "P5",
    26: "P6",
    31: "Pb",
    33: "Pd",
    38: "PP",
    39: "H0",
    40: "H1",
    41: "H2",
    42: "H3",
    43: "H4",
    44: "H5",
    45: "H6",
    46: "H7",
    47: "H8",
    48: "H9",
    49: "HA",
    50: "Hb",
    52: "Hd",
    53: "HE",
    54: "HF",
    55: "HH",
    57: "HP",
    65: "C7",
    112: "bH",
    116: "F1",
    134: "L0",
    135: "L1",
    136: "L2",
    138: "L4",
    139: "L5",
    141: "L7",
    142: "L8",
    143: "L9",
}
