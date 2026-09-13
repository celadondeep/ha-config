# Eimo Solis Inverter 4.2.1

Site-specific extension of hultenvp/solis-sensor 4.0.1 (Apache-2.0), based
on commit `6e360a073b8276bfa3140f003e9c0eeb3d10f63c`.

The `single_slot_control` configuration option replaces the upstream control
entities with confirmed controls and one charge/discharge slot. Telemetry
and controls share one HTTP client, a 300-second read budget and adaptive
300/600/1200-second error recovery. Every physical write waits at least
360 seconds and a later matching register read before another write.
An accepted API response is never presented as a confirmed device state.

Version 4.2.1 also enforces 300 seconds of network silence after startup or
reload. Reading is scheduled from response completion, not from telemetry
timestamps or fixed clock-aligned five-minute frames. Early, delayed and
repeated telemetry cannot open or move those request deadlines. Confirmation
reads also honor the monotonic write-settling deadline.

The Eimo model 3330 uses the readable CID 5162 ON/OFF variant and a
100-watt unit for CID 499. These model-specific choices have live evidence;
they are not a claim of compatibility with every Solis inverter.

Runtime code does not depend on `solis_cloud_control`. Its register behavior
was compared with the official Solis control documentation and mkuthan's
implementation. The queue and HA adapters were independently written.
See the retained LICENSE for the upstream code license.

Deployment, monitoring, ON/OFF evidence, limitations and rollback are in
[the migration record](https://github.com/celadondeep/ha-config/blob/main/docs/eimo_unified_solis_2026-09-12.md).
The matching tests are `tests/test_solis_confirmed_controls.py` in ha-config;
run with `python -m unittest discover -s tests -p test_solis_confirmed_controls.py`.

This is a customized build maintained in ha-config pending a dedicated fork.
Installing the upstream HACS package again can replace these custom files.
