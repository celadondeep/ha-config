# 2026-09-13: predictive battery headroom and dynamic Eimo telemetry

## Evidence and cause

Inspected today's complete available SOC/atomic-plan history and 1,000+
horizon records per site (00:00–17:45 Europe/Vilnius), plus live Python,
configuration and cloud request logs. This is not a measurement of lost PV.

| Site | Morning calibrated PV forecast, approximately | PV recorded by 17:40 | Late buffer behavior |
| --- | ---: | ---: | --- |
| Namai | 13 kWh | 16.6 kWh | TOU buffer first requested at 13:51:56, SOC 87%; later SOC 99% |
| Eimo | 12 kWh | 15.3 kWh | Short early request at 13:21; subsequent telemetry/control gaps; later SOC 100% |

The preferred upper SOC was 85% (hardware maximum minus 15 points), with
two-point start hysteresis: the separate buffer waited for 87%. Cumulative
PV bias reacted slowly to stronger afternoon generation after a cloudy
morning. The longer P10 budget also included the following cloudy evening,
which could veto useful earlier discharge. Rising SOC continuously raised
the 0.75-kWh burst cutoff, generating repeated target changes.

Eimo has an independent execution problem: a Self-Use write at 10:46:28
returned HTTP 502 at 10:46:29. Later successful register reads still showed
Feed-In Priority, so the conservative queue did not send another command.
This is distinct from insufficient headroom calculation. A 502 is not
proof of rate limiting or proof that a write was applied.

## Deployed policy

AppDaemon model `4.3-predictive-headroom`, shared by both sites:

- Add 8 SOC percentage points of planning headroom. With hardware max 100%,
  preferred upper SOC becomes **77%**, not a hardware charge limit.
  Extra modelled room: Namai 1.28 kWh; Eimo approximately 1.15 kWh.
- The same preferred ceiling is used in the next-solar-day dawn budget.
  Existing latest-feasible night scheduling and minimum SOC remain intact.
- Look ahead four hours for avoidable capacity clipping, after accounting
  for household demand, PV's use of the 1-kW export limit and battery power.
  A short discharge can start below 77% when remaining export opportunity
  is becoming insufficient. Allow 5 minutes execution margin for Namai and
  30 minutes for Eimo's intentionally slow confirmed command sequence.
- Protect P10 household demand through tonight and the next credible
  recharge opportunity, plus comfort SOC and the configured export floor.
  A second cloudy evening no longer automatically vetoes this short buffer.
- Blend fresh measured PV into the first forecast hour with at most 50%
  weight, decaying to zero. Do not extrapolate a brief sunny spike all day.
- Each new target step remains at most 0.75 kWh. Hold an outstanding cutoff
  stable as SOC rises; never keep it below a newly higher safety reserve.
- No forced export with missing grid confirmation, invalid forecast,
  zero export allowance, manual override or storm protection. No BMS SOC,
  charging-current or grid-charging settings were changed.

This is a bounded forecast policy, not a guarantee of never filling the
battery. Cloud outages, export limits and forecast errors can still prevent
the requested discharge. P10 protection is a modelled reserve, not a promise
that no grid import will occur.

## Solis Inverter 4.3.0 telemetry

Replaces 4.2.1's rigid completion-to-next-read interval **only for inverter
telemetry in the single-slot profile**:

1. Predict the next source update from Solis `dataTimestamp`, a cadence near
   300 seconds and a 15–90-second adaptive publication margin.
2. A successful response containing old data permits one extra inverter
   telemetry read after 60 seconds. A newly observed sample already more
   than one period old may use that same single probe.
3. No more than two actual inverter telemetry requests in any rolling
   300 seconds; at least 60 seconds after completion before another read.
4. The extra read does not fetch station data or force register refresh.
   Other reads retain 300-second limits. Any HTTP/API failure cancels the
   fast probe and closes the shared channel for 300/600/1200 seconds.
5. Startup/reload still imposes 300 seconds of network silence. Discovery's
   already-received data is published locally, without waiting a second cycle.
6. Physical writes still require 360 seconds **and a later matching register
   read**. No clock-setting writes, ping writes or catch-up command credits.

Existing health entities expose next telemetry request, phase, learned
period, margin, extra reads and rolling read/write counts. Existing request
logs record endpoint, result and duration without credentials.

## Validation and rollback

- 59 integration regression tests; 14 predictive-headroom tests.
- Python compilation and HA configuration validation passed before restart.
- All 11 live target files verified byte-for-byte against deployment hashes.
- Backup: `/homeassistant/backups/energy-dynamic-headroom-20260913T145457Z`.
  Its manifest records exact before/after hashes, including the new file.
- HA Core restarted once; AppDaemon stopped during the four-file replacement
  and started after HA returned. No automatic integration reload loop.
- To undo: restore the 10 original files from that backup; archive/remove
  only the added `custom_components/solis/telemetry_schedule.py`; validate,
  restart HA and AppDaemon, verify states. Do not restore an entire HA backup.

Integration and HA evidence live in `celadondeep/ha-config` main. AppDaemon
source and its new tests live in `celadondeep/Solis`, branch
`codex/eimo-unified-20260912`; its older main branch is not the deployed source.

Live post-start verification is recorded below when completed.
