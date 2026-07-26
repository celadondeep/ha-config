# Architektūra

## Dvi elektrinės — NIEKADA nemaišyti

| | Namai SE (1-a) | Eimo SE (2-a) |
|---|---|---|
| Vieta | Šeškinių k., Bartninkų sen., Vilkaviškio r. (54.456, 23.024) | Gražiškiai, Vilkaviškio r. (54.468, 22.921) |
| Ryšys | **Modbus** (telemetrija+režimas) **+ SolisCloud** (slotams, pridėta 2026-07-21) | **Solis Cloud** (solis + solis_cloud_control) |
| Inverteris | Solis S6-EH1P, SN 1033300254110046 | 1033300254190112 |
| Entities | `solis_s6_eh3p_*` (Modbus), `inverter_control_1033300254110046_*` (cloud) | `*_eimo`, `inverter_control_1033300254190112_*`, `solis_inverter_1033300254190112_*` |
| Baterija | 16 kWh; naudinga 14.4 (10–100 %) | ~14.3 kWh; naudinga 13.6 (5–100 %) |
| SOC dugnas | **10 % = FIZINIS BMS dugnas** (rodmuo 10 ≈ tikras 0) | 5 % (HW over-discharge), slot min 6 |
| kWh / 1 % SOC | 0.16 | 0.1434 |
| Valdymo failai | `automations.yaml`, `energy_manager.py` | `packages/eimo.yaml`, `energy_manager_eimo.py` |
| Baterijos ženklai | battery_power_net: + iškrauna, − kraunasi | battery_power: + KRAUNASI, − iškrauna (atvirkščiai!) |
| Tinklo ženklai | grid_power_net: + importas, − eksportas | grid_total_power: + EKSPORTAS, − importas (atvirkščiai!) |
| Paleista į tinklą | **2026-05-09 ~13–15 val.** (tiksliai, iš ESO istorijos) | ~2026-02-01 |
| ESO paskyra | Integruota (obj. 220588) | NEpajungta (pranešimai/bankas nematomi) |

## Atsakomybių padalijimas

- **AppDaemon TIK SKAIČIUOJA** (target_soc, prognozės, ekonomika) ir publikuoja
  sensorius. Inverterių NIEKADA nevaldo.
- **Inverterius valdo tik automations.yaml / packages/eimo.yaml** — per
  work_mode ir slotus.
- **Namai — VISKAS per Modbus** (telemetrija, režimas, laiko langai). Modbus
  TOU langai VEIKIA (2026-07-22 ištaisyta — 07-21 „slotai negyvi" buvo klaida,
  skaitytas ne tas registras: TOU būseną rodo 43110, ne 33132). `solis_cloud_
  control` pridėta be reikalo — nenaudoti valdymui. Eimo — viskas per cloud.
- **Iškrovimas — tik per slotus.** Overdischarge parametras NIEKADA neliečiamas.
- **Dienos režimas pagal prognozę**: aukšta diena → **Feed-in Priority**
  (1 kW į banką + baterija kraunasi), nuosaiki → **Self-Use**. Feed-in
  NEnukerpa (patikrinta gyvai 07-22). Žr. `valdymo_logika.md` §0.
- AppDaemon `set_state` visada su `str(round(x,2))` — AD 4.5.13 išmeta
  state=0/0.0 iš POST (0==False bug).

## Komponentai

- **HA core** (HAOS) — `/config`, git → `celadondeep/ha-config`.
- **AppDaemon addon** — `/config/appdaemon/apps`, atskiras git →
  `celadondeep/Solis`. Konteineryje `/config` rodo į addon'o vidų, todėl
  keliai per `__file__`.
- **Solcast** (HACS) — viena svetainė („seskiniu_2", kalibruota Namų
  stogui); Eimo tą pačią prognozę skaliuoja savo korekcijos koeficientu.
- **custom_components/eso** — ESO savitarnos integracija (žr. eso.md);
  upstream `algirdasc/hass-eso` (mūsų PR #39, #40).
- **Kasdienis auditas** — crond 05:00 + headless `claude -p`, procedūra
  `claude/daily_energy_review.md`; pilnas mandatas taikyti patikimus
  pakeitimus tiesiai (kai git medis švarus).

## Duomenų saugojimas

- `home-assistant_v2.db` — states 10 d., ilgalaikė statistika amžinai
  (įsk. ESO valandinius `eso:energy_*_220588` nuo 2026-04-01).
- AppDaemon būsenos failai: `consumption_model*.json`,
  `forecast_correction*.json`, `target_soc*.json` (apps kataloge);
  `eso_session.json`, `eso_seen_messages.json` (/config).
- Transkriptai (.jsonl) auto-trinami po 24 h (cron).
