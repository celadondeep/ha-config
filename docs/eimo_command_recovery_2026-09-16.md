# Eimo command recovery and planner execution fixes

Solis integration **4.4.0**, shared planner **4.4-command-recovery**.

## Incident and scope

At 22:14 LT on 2026-09-15 the Eimo plan requested sleep, slot 1 was OFF,
but the inverter was ON in Feed-In Priority. The queue was still waiting
for a Self-Use write attempted on 2026-09-13 at 10:46 LT. Successful reads
had been returning a different mode for two days, with no terminal outcome.

The new full-slot diagnostics subsequently exposed enabled CID 5927,
the sixth discharge slot. Checking only the visible slot 1 was insufficient
to establish that all forced discharge schedules were disabled.

The integration/package changes affect Eimo. Shared planner fixes apply
to both plants; their hardware SOC protections and 1 kW export limits remain.

## Changes

- After a write, retain the minimum 360-second interval and real device readback.
  Two complete mismatching reads separated by at least 300 seconds retire an
  unconfirmed attempt as failed, never as successful. Incomplete/failed reads
  reset that evidence. Restart requires new readback evidence.
- Retry only the currently desired state using a fresh snapshot. Failed command
  registers have persisted 900/1800/3600-second retry backoff. Other required
  actions can proceed; an old mode failure cannot indefinitely prevent power OFF.
- Verify only the requested mode bits and required TOU bit. Unrelated register
  flags may change without falsely preventing confirmation of the requested setting.
- Recover queue persistence failures with a bounded local retry. A failed save
  before HTTP prevents transmission; a failed reconciliation save also blocks
  further writes until persistence succeeds. Do not blindly replay the old write.
- Expire unsent manual targets after 30 minutes. Reject contradictory automatic
  slot targets and stop the opposite physical slot before enabling another one.
- Publish the current atomic plan explanation and a 180-second source expiry
  every evaluation, retaining the revision/commit timestamp for unchanged targets.
  Repeated executor calls cannot extend an expired source plan.
- Once the current night's discharge is committed, declining SOC no longer
  shifts its start into the future and sends it back to sleep. A new target,
  reaching the cutoff, production, or invalid inputs can still stop discharge.
- A non-confirmed grid connection prevents forced export and scheduled power OFF,
  including at the planner hard floor. Hardware battery protections still apply.
- Do not continue the daytime buffer solely because an earlier buffer was active
  after the predicted PV surplus has disappeared. Clear obsolete buffer diagnostics
  when entering the night branch.
- A sleeping inverter does not need a mode change merely to satisfy diagnostics.
  Pending hidden-slot cleanup remains `applying` until readback even if all visible
  entity values already match the plan.
- Expose active/missing slot registers, terminal failures, recovery count, command
  age, source lease and retry deadlines. API health distinguishes stalled/degraded
  control from a working transport. Extend existing HA monitoring to those states.

No keep-alive control writes or faster command loops were added. Telemetry retains
the bounded dynamic schedule from 4.3.0; ordinary register reads remain at least
300 seconds apart, and writes remain at least 360 seconds apart.

## Validation and deployment

94 offline tests passed: 73 integration/queue tests in ha-config and 21 shared
planner tests in the Solis application repository. Scenarios include late results,
partial reads, expired plans, restart, persistence failure, opposite slots, mode
bit preservation, night continuation, grid loss, SOC limits and planning headroom.
The existing telemetry timestamp assertion now uses millisecond tolerance to
avoid a sub-microsecond floating-point roundtrip failure.

All 14 changed live files passed checksum verification; Python/JSON/YAML parsing
passed, and HA's full configuration check returned valid before restart.
Backup: `/homeassistant/backups/eimo-command-recovery-20260915T193409Z`.
The backup's manifest records original and deployed hashes. To roll back, stop
AppDaemon, restore only these backed-up files, validate HA configuration, restart
HA for integration Python, restart AppDaemon, and restore the executor's prior
enabled state after checking the active plan. Do not restore the entire HA system.

HA restarted at 22:35 LT on September 15. Both planner instances subsequently
reported 4.4-command-recovery without AppDaemon errors. At 22:55:52 the new queue
automatically retired the old mode command after spaced mismatching reads.

The Eimo executor was paused for deployment at 22:34 and remained paused across
the interrupted work session. It was restored at 09:56 LT on September 16.
It made no new automatic writes during that pause; the inverter remained ON.
This period is not a successful live test of overnight sleep control.

At 09:56:08 SolisCloud accepted the old sixth-slot disable command. At 10:02:09
a later real batch read confirmed CID 5927 OFF, no other slot enabled, no missing
slot register, and `unused_slots_off=true`. The queue recorded that confirmation
and continued reconciling the current plan. The target at this daytime check is
inverter ON, both visible slots OFF, Self-Use while SOC is at the protected floor.
