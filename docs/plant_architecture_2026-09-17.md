# Plant architecture and rolling consumption — 2026-09-17

The user requested a reusable structure for Namai (Modbus), Eimo (SolisCloud)
and future plants, then a rolling daily/hourly consumption profile. Deployment
uses the existing two repositories; AppDaemon source remains on the Solis
`codex/eimo-unified-20260912` branch.

## Deployed behavior

- Both sites use the same planner, consumption model and dashboard templates.
  Site data lives in `energy_system/sites/*.json`; shared defaults, portfolio
  data and class generation replace duplicate entity maps and startup wrappers.
- HA's two existing executor automation IDs now bind to
  `energy/modbus_executor.yaml` or `energy/solis_cloud_executor.yaml`.
  `custom_templates/energy_plan.jinja` is the common freshness/target contract.
- Both live dashboards have four corresponding views: Energija, Analizė,
  Atsipirkimas, Vartojimas. Existing URLs and entity IDs are preserved.
- Consumption uses 30 completed local calendar days and actual observed daily,
  hourly and weekday means. Incomplete hourly days and isolated daily spikes
  are excluded with visible diagnostics. Forecast weekday effects are shrunk
  towards the overall mean. Previous hardcoded seasonal multiplication is
  only a fallback before a rolling model has enough observations.
- One daily local HA recorder query and one bounded delayed retry maintain the
  hourly model. This adds no SolisCloud calls. Cache and atomic model writes
  protect restart and history-query failures.

## Evidence from the initial window

2026-08-18 through 2026-09-16, Europe/Vilnius:

| Site | Daily mean | Usable daily observations | Complete usable hourly days |
|---|---:|---:|---:|
| Namai | 17.16 kWh | 29 | 26 |
| Eimo | 9.20 kWh | 28 | 26 |

Eimo's August 23/24 daily history contained approximately 50.19/111.19 kWh;
these dates are statistical outliers. Recorder hourly data has a zero-total
day on August 23 and the large accumulated jump on August 24. They are excluded
without claiming the exact underlying meter/cloud cause is proven.

The old model combined a 14-valid-record median, weekday estimates across the
whole archive and an indefinite hourly EMA. It was not a consistent 30-day
window. The new window advances by calendar dates and never silently fills
missing observations with zeros or pulls older days in to reach 30 samples.

## Deployment and recovery

Backup: `/homeassistant/.codex-backups/plant-architecture-20260917T163929Z`.
Its manifest covers 25 changed/new files; `files/` also contains both original
learned consumption JSON models. The original blueprint files had been created
through HA's native blueprint API; native YAML normalization was checked
semantically before comparing deployment hashes.

AppDaemon stopped at approximately 19:41:12 LT; all apps initialized again at
19:41:21. HA Core stayed running. Both executor automations remained enabled.
Custom templates were reloaded, HA configuration validation returned valid
with no errors, then automations were reloaded. Local statistics refreshed at
19:41:46 and both consumption profiles reported version 3 / status ok.

A rollback restores only files named in this backup manifest (removing files
whose `before` hash was null), plus the two model JSON files, during a brief
AppDaemon stop. Then start AppDaemon, reload custom templates, run the HA config
check and reload automations. Do not restore a whole HA backup for this change.
Do not restore learned state after unrelated later learning without review.

## Validation

- 52 AppDaemon tests: 21 existing planning/headroom, 14 profile/architecture,
  17 rolling consumption and history-failure tests.
- 10 shared HA plan-contract tests, in addition to the existing 73 cloud and
  control tests. CI installs Jinja2 and includes blueprint/template paths.
- Python compilation, generated dashboard JavaScript compilation and HA's
  actual configuration validator.
- Live shared macro returned true for both valid plans. Both planners were ok,
  core states normal and executor automations on after reload.
- Native Lovelace config returned all four views for both live dashboards.
- Browser inspection reached HA login; no authenticated screenshot was available.
  This limits visual verification, not the native configuration/data checks.

This is not a claim that every unrelated HA automation is now generic, that
all possible control bugs are eliminated, or that a short deployment check
proves long-term cloud availability. Old auxiliary home guards remain in
site-specific HA config. Solis integration transport/queue code is unchanged.

## Completion verification — 2026-09-18 05:46 LT

Both requested tasks are complete and deployed. The overnight verification
confirmed both planners and executors `ok`, both cores `normal`, both executor
automations enabled, and Eimo's command queue `idle` with no outstanding write.
Cloud health was `healthy`; the monitoring snapshot showed three API reads
and zero writes in the preceding five minutes, with zero writes in the last
hour. Earlier cloud failures remain in diagnostic history; recovery is not
represented as uninterrupted connectivity.

Both consumption models refreshed automatically at 00:20 LT. The persisted
window advanced to **2026-08-19 through 2026-09-17**, excluding September 18.

| Site | Daily mean | Accepted daily samples | Complete hourly days |
|---|---:|---:|---:|
| Namai | 17.17 kWh | 29 | 26 |
| Eimo | 9.24 kWh | 28 | 26 |

The saved JSON contains all 24 hourly and seven weekday values, matching
window bounds and valid source status. All 25 deployed file hashes still match
the deployment manifest. AppDaemon's available container log returned no
ERROR entries.

Both published source revisions passed GitHub CI:
- [AppDaemon validation](https://github.com/celadondeep/Solis/actions/runs/35248825296)
  for `a6b2f163f7176eb1bdd87b38d7e3fe5cfc492580`.
- [HA validation](https://github.com/celadondeep/ha-config/actions/runs/35248826329)
  for `ee00e149d8b061be5c9c7a396c7889b1a1638df3`.

No additional control command, software reload or inverter query was needed
for this completion check. The browser-only visual verification limitation
noted above remains; native dashboard configuration and data were verified.
