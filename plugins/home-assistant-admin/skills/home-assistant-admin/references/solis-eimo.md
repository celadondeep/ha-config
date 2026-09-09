# Solis / Eimo recovery workflow

Use for unstable SolisCloud connections, Eimo plant data, `solis_cloud_control`, `solis`, cloud polling, stale values, and inverter control.

## Recovery priority

When a previously working mechanism exists, first restore a minimal proven communication path. Optimize polling only after a successful request path is confirmed.

## Diagnose in this order

1. Integration/config-entry setup state.
2. Earliest current exception after setup/restart.
3. Endpoint being called.
4. Timeout / device-offline / auth / rate-limit / empty-discovery response.
5. Historical successful endpoint and request sequence, if available.
6. Whether the failure is discovery-only while a direct device request can still work.

## Design principles

- Do not make static discovery a hard dependency for every runtime refresh when cached metadata is sufficient.
- If direct batch reads previously worked, allow the integration to start from cached non-secret inverter metadata and attempt the proven batch read path.
- A failed first cloud refresh should not necessarily keep the whole config entry in permanent `setup_error` if the coordinator can recover later.
- Entity availability must tolerate `coordinator.data is None`.
- Keep retries bounded; avoid a single update cycle blocking for several minutes.
- Poll faster only while recovering/stale if API limits and service stability permit it.
- Once stable, use a conservative interval.
- Track last successful cloud contact and stale-data age separately from entity availability where practical.

## Validation after change

After restarting Home Assistant:

1. Confirm the config entry becomes loaded rather than setup-error.
2. Check fresh logs for the expected direct/batch API path.
3. Record API return code or timeout.
4. Verify control and telemetry entities become available only when valid data exists.
5. Ensure there is no rapid request loop.
6. If direct communication works, then implement adaptive polling/diagnostics as a separate second-stage improvement.

## Safety

Never place SolisCloud API secrets, passwords, tokens, station IDs, inverter serial numbers, or account identifiers inside a reusable global skill. Read such values from the live Home Assistant config or user-provided current context when needed.
