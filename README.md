# Midea M-Thermal Arctic for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Release](https://img.shields.io/github/v/release/gompper/ha-midea-thermal-arctic)](https://github.com/gompper/ha-midea-thermal-arctic/releases)
[![CI](https://github.com/gompper/ha-midea-thermal-arctic/actions/workflows/ci.yml/badge.svg)](https://github.com/gompper/ha-midea-thermal-arctic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/gompper/ha-midea-thermal-arctic)](LICENSE)

A Home Assistant custom integration for the **Midea M-Thermal Arctic R290** heat pump over Modbus.

> [!WARNING]
> **Unofficial project, use at your own risk.** This integration is not affiliated with, endorsed by or supported by Midea. It reads from and writes to your heat pump's controller (power, mode and target temperature). It is provided "as is", without warranty of any kind, and the authors accept no liability for damage to your heat pump, your building or anything else, for lost manufacturer warranty, or for any other consequence of using it. See the [license](LICENSE).
>
> Wiring the RS-485 connection means opening the wired controller. Disconnect power first, follow the manufacturer's manual and local regulations, and leave it to a qualified person if you are unsure.

It is set up in the UI, knows the heat pump's register map itself, and uses the shared Modbus connections introduced in Home Assistant 2026.9: if another Modbus integration talks to the same gateway, both share one connection instead of competing for the bus. No `modbus:` YAML is needed.

## Supported hardware

| | |
|---|---|
| Heat pump | Midea M-Thermal Arctic R290, tested on the 4 kW unit (the test data comes from a 10 kW unit) |
| Connection | RS-485 on the **wired controller** (H1/H2), not the outdoor unit |
| Gateway | Any Modbus TCP-to-RTU gateway, e.g. Elfin EW11A (WiFi) or EE11A (Ethernet) |
| Home Assistant | 2026.10 or later |

Only what the tested units have is supported: one zone of water temperature control, without domestic hot water, tank booster or backup heaters. Other M-Thermal models likely share the register map but are untested. The Midea documentation notes that non-R290 units report energy unscaled, which this integration does not handle yet.

## Wiring

Connect the gateway's RS-485 terminals to the wired controller:

| Gateway | Wired controller |
|---|---|
| A (+) | H1 |
| B (−) | H2 |
| E / shield | E_H |

This follows the wired controller's installation manual. Some older Midea Modbus documents show H1 and H2 the other way round. If the heat pump never answers, swapped lines are the most common cause; swapping them is harmless. HA/HB on the controller is the link to the hydraulic module, not Modbus.

A ground wire is not needed on a short cable.

## Gateway settings

| Setting | Value |
|---|---|
| Baud rate | 9600 |
| Data bits / parity / stop bits | 8 / none / 1 |
| Protocol | **Modbus** (TCP-to-RTU gateway), not transparent TCP |
| Network | TCP server, port 8899 (the Elfin default) |

On Elfin gateways, also consider disabling the serial CLI escape (`+++`), which is not needed.

The Modbus address (unit ID) is set on the heat pump's wired controller. Midea ships it as **1**.

## Installation

**HACS** (recommended):

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gompper&repository=ha-midea-thermal-arctic&category=integration)

The button adds this repository to HACS in your Home Assistant. Then download *Midea M-Thermal* and restart Home Assistant. Without the button: in HACS, open the menu → *Custom repositories*, add `https://github.com/gompper/ha-midea-thermal-arctic` with type *Integration*, then download as above.

**Manually**: copy `custom_components/midea_m_thermal/` into your configuration directory's `custom_components/` folder and restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Midea M-Thermal.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=midea_m_thermal)

Or go to **Settings → Devices & Services → Add Integration → Midea M-Thermal**, and enter the gateway's host, port and the heat pump's unit ID. The heat pump is read before anything is saved, so a wrong address or unit ID is reported right away.

To change them later, use **Reconfigure** on the integration entry. Entities and their history are kept.

## Entities

With the default device name *Heat pump*, entity IDs start with `heat_pump_`.

### Controls

| Entity | Register | Notes |
|---|---|---|
| Power (switch) | 0, bit 1 | Zone 1 water temperature control. Other bits are left alone |
| Mode (select) | 1 | Auto, Cooling, Heating |
| Target temperature (number) | 2, low byte | Min/max follow the active mode, from the heat pump's own limits (registers 201-204): e.g. Cooling 5-25 °C, Heating and Auto 25-55 °C |

Cooling and heating share one setpoint register, so switching to Cooling with a setpoint above the cooling maximum pulls it down to that maximum. Every setpoint write re-reads the mode and is clamped to its range, even if the mode was changed on the wired controller since the last poll.

### Sensors

| Sensor | Register | Unit |
|---|---|---|
| Operating state | 101 | Idle, Cooling, Heating |
| Operation mode | 199 | Off, Cooling, Heating, Domestic hot water |
| Compressor frequency | 100 | Hz |
| Water inlet temperature (Tw_in) | 104 | °C |
| Heat exchanger outlet temperature (Tw_out) | 105 | °C |
| Condenser temperature (T3) | 106 | °C |
| Outdoor temperature (T4) | 107 | °C |
| Discharge temperature (Tp) | 108 | °C |
| Suction temperature (Th) | 109 | °C |
| Water outlet temperature (T1) | 110 | °C |
| Water temperature delta | T1 − Tw_in | °C |
| High pressure (P1) | 116 | kPa |
| Low pressure (P2) | 117 | kPa |
| Outdoor unit current | 118 | A |
| Outdoor unit voltage | 119 | V |
| Outdoor unit power | current × voltage | W |
| Error code | 124 | |
| Water flow | 138 | m³/h |
| Heating capacity | 148 | kW |
| Power consumption | 150 | kW |
| COP | 151 | |
| Cooling capacity | 180 | kW |
| Cooling power consumption | 181 | kW |
| EER | 182 | |
| Energy consumption | 143-144 | kWh |
| Energy produced | 145-146 | kWh |
| Heating energy produced | 158-159 | kWh |
| Heating energy consumption | 162-163 | kWh |
| Lifetime COP | 164 | |
| Cooling energy produced | 165-166 | kWh |
| Cooling energy consumption | 169-170 | kWh |
| Lifetime EER | 171 | |

Notes:

- **Power consumption**, **Heating capacity** and **COP** cover heating only and read 0 in Cooling mode. The Midea table has their cooling counterparts in 180-182: *Cooling power consumption*, *Cooling capacity* and *EER*. These have not been checked on a cooling unit yet. *Outdoor unit power* is a live figure in every mode, though it excludes the water pump.
- **COP** and **EER** are unknown while the compressor is idle and when the register spikes above 10, which it does while the compressor ramps up. The same applies to the lifetime ratios.
- **Energy consumption** and **Energy produced** cover all modes; the heating and cooling counters split them up. Their ratio is the unit's overall seasonal performance.
- The energy counters keep their last value while the heat pump is unreachable and ignore small dips, so the Energy dashboard and long-term statistics never see a false meter reset. A counter that has never counted, such as the cooling ones before the first cooling run, is unknown.
- A temperature whose sensor is not fitted or broken is unknown rather than a made-up value such as 127 °C or 255 °C.
- The device model shows the unit's nominal capacity (register 123).

## How it talks to the heat pump

Each poll, every 30 seconds, makes two requests: registers 0-2 and one block of 100-199. The setpoint limits in 201-204 are read once, one register per request, because the controller refuses multi-register reads above 200. If it refuses them entirely, the documented ranges are used.

A dropped connection makes entities unavailable until the next successful poll, without reloading the integration. After three timeouts in a row, the connection is re-opened, because some serial gateways keep their socket open while the RS-485 side has stopped answering.

## Troubleshooting

- **Cannot connect**: check that the gateway runs in Modbus mode (not transparent TCP), the port, and the unit ID on the wired controller.
- **"A device answered, but not like a Midea M-Thermal heat pump"**: the unit ID reaches a different device.
- **Reporting a problem**: download the diagnostics from the device page. They contain every register the integration reads, which is often enough to reproduce the issue in a test. Attach them to a [new issue](https://github.com/gompper/ha-midea-thermal-arctic/issues/new/choose).

## Development

The register map lives in `custom_components/midea_m_thermal/m_thermal_modbus/`, a device library on [modbus-connection](https://home-assistant-libs.github.io/modbus-connection/) with no Home Assistant imports. The integration around it follows Home Assistant's [Modbus developer guide](https://developers.home-assistant.io/docs/modbus/introduction).

`modbus-connection` is not a requirement of this integration: it comes with Home Assistant's `modbus` integration, which pins the version (4.12.3 in Home Assistant 2026.10.0, 4.12.4 in 2026.10.4, 4.12.7 in 2026.11). The device builds on its `model.Device` base class, which 4.10.0 in Home Assistant 2026.9 lacks; hence the 2026.10 minimum. Write against that version's API rather than the latest documentation, which describes newer releases.

Run the tests, which use Home Assistant 2026.10.4 (the newest release `pytest-homeassistant-custom-component` covers) and a mock heat pump loaded with a real register dump (`tests/fixtures/registers.json`):

```bash
uv venv --python 3.14
uv pip install -r requirements_test.txt
.venv/bin/pytest
```

### Releasing

1. Raise `version` in `custom_components/midea_m_thermal/manifest.json` and merge it to `main`.
2. Publish a GitHub release whose tag is that version with a `v` in front, e.g. `v1.2.0`. The release workflow fails if tag and manifest disagree.

For a beta, use a version like `1.2.0b1`, tag it `v1.2.0b1` and mark the GitHub release as a pre-release. It can be released from a branch before merging. HACS offers it as an update only to users who enable beta versions for this repository; anyone can install it by picking the version in HACS's *Redownload* dialog.

HACS offers the new release to users as an update.

## Credits

This integration builds on [mkroiss/midea-thermal-artic-r290-modbus](https://github.com/mkroiss/midea-thermal-artic-r290-modbus), a YAML-based Home Assistant setup for the same heat pump. Its register documentation, the behaviour observed on a real unit (setpoint limits per mode, Power consumption reading 0 in Cooling, COP spikes, which register blocks can be read in one request) and the register dump used by the tests all come from there.

## License

[MIT](LICENSE). No warranty, see the notice at the top.

Midea and M-Thermal are trademarks of their respective owners and are used here only to name the hardware this integration works with.
