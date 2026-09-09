# Eimo SolisCloud Stage-1 recovery

Use this runbook for the current Eimo inverter recovery implementation.

## Scope

Stage-1 is intentionally scoped to exactly one inverter serial:

`1033300254190112`

Do not apply the cached profile or Eimo recovery intervals to other Solis inverter entries.

## Why Stage-1 exists

Current SolisCloud startup can fail at:

`/v1/api/inverterDetail`

Historical Eimo logs proved that the same inverter could successfully communicate through:

`/v2/api/atReadBatch`

The recovery design therefore removes startup discovery as a hard dependency for Eimo and immediately allows the normal batch coordinator path.

## Cached non-secret inverter profile

For Eimo only:

- model: `3330`
- version: `09000C`
- machine: `S6-EH3P10K02-NV-YD-L`
- energy storage control: `40`
- smart support: `1`
- generator support: `1`
- collector model: `WL`
- power: `10.0 kW`
- parallel number: `1.0`
- parallel battery: `0`
- TOU V2 mode: `43605`

The serial itself is part of the implementation scope, not a reusable account credential. Never add SolisCloud API credentials or account secrets to this file.

## Current code behavior

Files:

- `custom_components/solis_cloud_control/inverters/inverter_factory.py`
- `custom_components/solis_cloud_control/coordinator.py`
- `custom_components/solis_cloud_control/entity.py`
- `custom_components/solis_cloud_control/__init__.py`

Eimo behavior:

1. Skip startup `inverterDetail`.
2. Return the cached profile above.
3. Set TOU V2 mode to `43605`, so the coordinator does not need the old individual CID 6798 startup read.
4. Poll using the normal `atReadBatch` set.
5. Eimo update interval: 1 minute.
6. Eimo batch retry budget: 30 seconds.
7. Eimo individual read retry budget: 30 seconds.
8. A failed first Eimo coordinator refresh does not leave the config entry permanently in `setup_error`.
9. Entities remain unavailable while coordinator data is missing or the last update failed.

Non-Eimo behavior remains upstream-like:

- 5 minute update interval
- 180 second batch retry budget
- 60 second individual retry budget
- mandatory first coordinator refresh
- normal inverter detail discovery

## Git safety

Pre-change backup branch:

`backup/eimo-solis-stage1-20260909`

Safe live deployment helper:

`scripts/deploy_eimo_solis_stage1.sh apply`

Rollback:

`scripts/deploy_eimo_solis_stage1.sh rollback`

Diagnostic helper:

`scripts/check_eimo_solis_stage1.sh`

Do not treat GitHub `main` as proof that live Home Assistant is updated.

## Live deployment sequence

When Home Assistant file/terminal tools are callable:

1. Read the four live target files and confirm the active config root.
2. Preserve live originals.
3. Deploy the exact validated `main` versions or run the safe deploy helper.
4. Validate Python syntax.
5. Restart Home Assistant Core.
6. Inspect fresh logs.
7. Confirm the Eimo `solis_cloud_control` config entry loads.
8. Confirm the request path is `/v2/api/atReadBatch`.
9. Classify the result:
   - success/API code 0 → Stage-1 communication restored;
   - B0072 → direct cloud path works but SolisCloud currently reports the inverter offline;
   - timeout on `atReadBatch` → discovery bypass worked, but the direct cloud path is also unreachable;
   - timeout on Eimo `inverterDetail` → Stage-1 is not actually active live;
   - Python/import error → rollback immediately.
10. Check affected Eimo control entities.

## Next stage only after a successful batch

Do not redesign everything before the first successful direct batch.

Stage-2 candidates:

- last successful cloud contact
- stale-data age
- adaptive recovery polling
- failure reason/state sensor
- slower stable interval
- background static-metadata refresh that never breaks live control
