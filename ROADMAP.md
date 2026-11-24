# Roadmap: an integration for every M-Thermal owner

Goal: anyone with a Midea M-Thermal heat pump (Arctic R290 first, then other models and rebranded units on the same controller) can install this integration and get every register of the Midea Modbus table that their unit supports, while nothing their unit does not have clutters Home Assistant.

The steps are ordered by risk. Each one is a small release (beta first, then stable) that can be reviewed and rolled back on its own. **Low-risk, read-only work comes first; anything that writes to a heat pump, changes how values are scaled, or depends on hardware nobody here can test comes last.**

## Ground rules for every step

- **Read first, write last.** A new register is added read-only. A control comes only after its readings have been checked on real units.
- **No guessed hardware.** What a unit reports as absent (function flags 198, 210, 211) is not created. What cannot be detected is created *disabled by default*, so owners can switch it on themselves.
- **Stable entity IDs.** Unique IDs never change; renaming or removing an entity needs a migration and a note in the release.
- **Every write to the maintainer's own unit is approved beforehand, one by one.** Installer and safety parameters (registers 200+) stay read-only for good.
- **Every behaviour is backed by a register dump** in `tests/fixtures/`, ideally from the user who reported it.
- **Beta before stable.** Each release goes out as `vX.Y.0b1` and is installed via HACS from the beta tag before it is promoted.

## Already shipped or in flight

| Release | Content | State |
|---|---|---|
| 1.3.0b1 | Status sensors, load outputs, function detection from 198/210/211 (#4) | merged |
| 1.3.0b2 | Heating capacity read as signed during defrost (#6) | beta, stable planned ~1 Dec 2026 |
| 1.4.0b1 | ECO, silent mode and level, climate curve on/off and number (#5) | draft, held until 1.3.0 is stable |

The roadmap below continues after 1.4.0 and does not change those PRs.

---

## Step 1 · 1.5.0: Device reports and tested-devices list

*Risk: very low. No change to entities or polling.*

Without dumps from other units, every later step is guesswork. This step makes it easy for owners to send one.

- Extend the diagnostics download with a **one-off survey**: every documented register (0-21, 100-199, 200-290 one by one, 700-703, 1000+ as far as the unit answers), each marked *ok*, *refused* or *zero*. Only runs when the user downloads diagnostics, never during normal polling. Include the sub-model (190), capacity (123), software versions (130, 131) and protocol version.
- New issue template **"Device report"** that asks for the diagnostics file, brand/model on the type plate, gateway and wiring.
- **Tested devices** table in the README (model, capacity, sub-model, gateway, reported by, integration version), filled from those reports.
- Short **"Is my heat pump supported?"** section: which controllers carry the Midea table, what a user can try safely, how to report.
- A test helper that turns a submitted diagnostics file into a fixture in one command.

Done when: at least one dump from a unit other than the two known R290 units is in `tests/fixtures/`.

## Step 2 · 1.6.0: Translations and documentation

*Risk: very low. Texts only.*

- Make English and German complete for every entity, state, option and error; add a CI check that both files have the same keys (and that `strings` match the code).
- Accept community translations (French, Italian, Dutch, Polish are the likely Midea markets) with a short how-to in the README.
- Generate the entity tables in the README from the register map, so docs and code cannot drift apart.
- Document each entity's register, unit, and in which situations it reads unknown.

## Step 3 · 1.7.0: Detection and disabled-by-default entities

*Risk: low. Read-only, but changes which entities exist.*

This is the core of "everything the unit supports, nothing else".

- Add a **probe at setup** that reads each optional register once and records whether the unit answers with a plausible value, refuses it, or reports a sentinel (0, 0xFFFF, 127 °C, 255 °C). Results are stored on the config entry and shown in diagnostics.
- **Policy per entity**, documented in the code:
  - function flag says *absent* → not created
  - flag says *present* or there is no flag, and the probe looks plausible → created and enabled
  - no flag and the probe is inconclusive → created **disabled by default**
- An **option "Show all entities"** in the options flow for units whose flags are wrong or incomplete. It creates every entity, disabled where the unit has no flag for it.
- A **"Re-detect hardware"** button (or reload) after changes in the installer menu, instead of today's "reload the integration".
- Entities that later turn out unsupported become unavailable, not deleted, so history survives.

Done when: the existing fixtures produce exactly today's entity set, and a fixture with all functions enabled produces the full set.

## Step 4 · 1.8.0: Read-only sensors for optional hardware

*Risk: low to medium. Read-only, but most of it cannot be checked on the maintainer's unit, so it ships as "experimental" until someone with that hardware confirms it.*

All gated by Step 3. Grouped so each can be its own beta if a group needs fixes:

- **Domestic hot water**: tank temperature T5 (115), DHW target (4 or 11/15 read-back), DHW operation status (198 bit 5), Pump_D, disinfection status (21 bit 4), DHW energy and power (172-178, 183-186).
- **Zone 2**: water temperature Tw2 (111), climate curve target (137), zone 2 power and setpoint read-back (0 bit 3, 2 high byte / 12), curve selection (6 high byte / 19), mixing pump.
- **Room temperature control**: Ta setpoint read-back (3), room thermostat demand.
- **Buffer tank**: Tbt1 / Tbt2 (120, 121).
- **Heaters and auxiliary sources**: IBH/TBH/AHS operating states and configured powers (250-252), solar input.
- **Status**: holiday home / away (5 bits 5, 8, read-only), SG ready / EVU signals (10), slave unit status (142).
- **Second refrigerant circuit** (EXV2/3, fan 2: 195-197) on larger units.

Done when: each group has a fixture from a real unit that has the hardware, or is marked experimental in the README.

## Step 5 · 1.9.0: Other models and refrigerants (read-only)

*Risk: medium to high. Wrong scaling silently corrupts the Energy dashboard and long-term statistics, which cannot be repaired afterwards.*

- Use the sub-model (190) to pick the **energy scaling**: R290 units report hundredths of a kWh, other units whole kWh (143-178, 1023-1024). Units with an unknown sub-model get the energy counters disabled until a report confirms the factor.
- Check other per-model differences in the table (e.g. 211 vs 273 for "other units", temperature resolution, single vs. three phase) and handle them in the device library, not in the entities.
- Rename the user-facing wording from "Arctic R290" to "M-Thermal" where it describes the whole family; keep the domain and entity IDs.
- **Cascade systems** (1000+ registers): one sub-device per slave unit, read-only, only when a cascade dump is available.
- Accept a model in the tested-devices list only with a dump.

Done when: at least one non-R290 unit has been confirmed by its owner, including energy counters over a few days.

## Step 6 · 1.10.0: Connection types and gateways

*Risk: medium to high. Every gateway behaves differently, and failures show up as dropped connections that are hard to debug remotely.*

- **Configurable poll interval and timeout** in the options flow, with safe limits.
- **Gateway quirks** collected in one place: single-client gateways (Elfin), gateways that split or refuse multi-register reads, read limits above register 200. Fall back to single-register reads automatically when a block read is refused.
- **RS-485 directly** (USB adapter on the HA host) through Home Assistant's shared Modbus connection, if `modbus-connection` supports serial for custom integrations by then.
- Documented setups for common gateways (Elfin EW11A/EE11A, Waveshare, USR-TCP232) and for sharing a gateway with other Modbus integrations.

## Step 7 · 2.0.0: Controls for optional hardware

*Risk: high. Writes to a heat pump the maintainer cannot test on.*

Only everyday settings, never installer parameters. Each control:

- exists only when its function is detected (Step 3) **and** its reading has been confirmed in Step 4;
- takes its limits from the unit's own registers where they exist, otherwise from the documented range, and is clamped before writing;
- reads the register back after writing and reports a mismatch;
- has been tested by at least one volunteer owner on a beta before it is released as stable.

Candidates, in this order: DHW on/off (15) and DHW target (4), zone 2 on/off (14) and setpoint (12), zone 2 curve (19), room temperature setpoint (3), forced DHW (7), forced TBH / IBH (8, 9, last, since they switch electric heaters), SG ready / EVU (10) only if a real use case comes up.

Deliberately left out: everything in 200-290 (installer settings), refrigerant leakage detection, C2 fault restore.

## Step 8 · HACS default catalog and quality

*Risk: organisational rather than technical, and hard to undo. Once listed, many users install it, and every breaking change reaches them.*

Only after Steps 1-7 have been stable for a while.

- Meet the HACS default requirements: description and topics on GitHub, releases, `hacs/action` and `hassfest` passing (already in CI), brand images (already present).
- Work through the relevant **Home Assistant integration quality scale** rules (config flow tests, diagnostics, reconfigure, translations, entity categories, unavailable handling) and document the result.
- Open the inclusion PR on `hacs/default`.
- Set up issue labels and a short support policy (what dump to attach, which models are supported).

---

## What is needed from the community

Most of Steps 4-7 depends on owners with different hardware. Each report with a diagnostics file moves a group of entities from "experimental" to "tested". The Device report template from Step 1 is the entry point.
