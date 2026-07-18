# Valdymo logika — paros ciklas

## Šeškiniai SE (Solis, lokalus Modbus)

### Rytas
- **04:40** — Solcast dienos prognozės snapshot (valandinės korekcijos mokymuisi).
- **05:30 / 06:15 / 06:45** — `morning_room_check` (AppDaemon): jei šiandienos
  planas (koreguotas × 1.25 marža × intradienos santykis) netelpa į laisvą
  vietą — target žeminamas (nuosaikią dieną ne žemiau 20). Naktinis slotas
  (langas iki 07:30) spėja padaryti daugiau vietos.
- **06:00** — `solis_morning_mode`: režimo pasirinkimas pagal DINAMINĮ
  slenkstį: `(100−SOC)×0.16 + likęs_vartojimas×0.5`. Prognozė aukščiau →
  **Feed-in Priority** (eksportas nuo pirmų vatų); žemiau → Self-Use.
  Audros režimas turi pirmenybę; nebaigta naktinė iškrova nekeičiama.
- **Inverterio įjungimas** — pagal `inverter_morning_on_time` (Solcast >100 W
  perkirtimas −30 min), Eimo PV >200 W realų signalą arba 10:00 fallback;
  taip pat ties atidėto iškrovimo sloto startu.

### Diena (07:00–19:30), `solis_daytime_feedin_tou` kas 15 min
1. **Floor variantas:** `room_shortfall > 1 kWh` ir SOC ≥ floor+5 → slotas
   su cut-off = floor (12): baterija laikoma prie dugno, viskas į banką.
   Gali perimti skutimo slotą (gilesnis cut-off svarbesnis).
2. **Viršūnės skutimas:** SOC ≥ lubos+1 → slotas su cut-off = lubos:
   **80** nuosaikią dieną (≤28 kWh), **90** aukštos gamybos. Diskriminatorius
   šakoms: cut-off ≥ 80 = skutimas, < 80 = floor.
3. **Dugno atsistatymas:** floor slotas pasiekė dugną → slotas OFF,
   Self-Use, saulė kelia iki floor+5, tada eksportas atsinaujina.
4. **Perteklius dingo** (<0.2) → floor slotas OFF, Self-Use, kaupiama.
- Apsaugos: `battery_protect` <11 % → Self-Use; `export_resume` >15 % →
  FiP (kai PV > namai ir liko >2 kWh prognozės).

### Vakaras / naktis
- **18:00–23:00 kas 30 min** — `evening_discharge_cycle` (AppDaemon):
  target = 100 − rytojaus vietos poreikis (battery_room_needed su 1.25
  marža); clamp [sezono min, 85]; nuosaikiai rytdienai ≥ 20 (sveikatos
  zona); audra → 100.
- **20:00** — `solis_evening_discharge`: jei SOC > target → naktinis TOU
  slotas su cut-off = target; **sloto startas skaičiuojamas atgal nuo
  gamybos pradžios** (~1 kWh/val + 0.5 h atsarga; >22 kWh dienai ~1 val
  anksčiau), ne ankstesnis nei 21:00 — SOC min pasiekiamas prieš pat saulę.
- **20:05–07:00 kas 5 min** — `solis_tou_recalc_5min`: atnaujina cut-off,
  pasiekus tikslą slotą išjungia; po iškrovos FiP/Self-Use pagal dinaminį
  slenkstį.
- **Naktinis inverterio išjungimas** (idle 130 W → off 30 W): kai iškrova
  baigta IR SOC ≤ target+1, ARBA kai slotas laukia atidėto starto (waiting).
  Pažadinimas: morning_on_time / sloto startas / Eimo PV / 10:00.
- Žemo SOC juostoje — atskiras naktinis išjungimas (churn apsauga).

## Eimo SE (cloud)

**Esminis skirtumas:** Eimo inverteris **Feed-in Priority režime baterijos
NEIŠKRAUNA** — todėl FiP nenaudojamas išvis. Bazinis režimas visada
**Self-Use**, visas eksportas iš baterijos — per slot1. Cloud API lėtas ir
rate-limituojamas — rašoma tik kai reikšmė keičiasi.

- **Diena** (`solis_daytime_discharge_eimo`, kas 15 min, 07:00–19:30) —
  veidrodinė Solis logika: floor variantas (cut-off = floor 6) pagal
  `eimo_room_shortfall`; viršūnės skutimas 80/26 kWh riba (90 aukštai
  gamybai); dugno atsistatymas +5 pp; re-arm floor+5.
- **20:00** — vakaro iškrovimas: slot1 su cut-off = target (clamp ≥6);
  startas taikomas į saulėtekį (sun.sun next_rising, 0.1434 kWh/%).
- **20:05–07:00** — recalc kas 5 min (rašo tik pasikeitus).
- Naktinio inverterio išjungimo nėra (cloud valdymu neįmanoma).
- Sveikatos zona: target ≥ 20 nuosaikiai dienai (BIG_DAY_KWH 26).

## Audros / ESO rezervo režimas (abi elektrinės atskirai)

`input_boolean.storm_mode` / `storm_mode_eimo` → momentinis pritaikymas
(toggle automatikos): eksportas STOP, krovimo slotas visai parai (tik
saulė), baterija namams neiškraunama, vakaro logika target=100.
Automatinis planavimas ESO atjungimams — žr. eso.md.

## Boileris (ESP32 — dar nepajungtas)

Logika paruošta `energy_manager`: strateginis leidimas pagal balansą,
taktinis valdymas pagal perteklių (SURPLUS_MIN 0.3 kW), SOC slenksčiai
(>90 % tikrinti, >95 % perteklius į vandenį). Pajungus reikės įrašyti
tikrus entity ID vietoj `sensor.boiler_temperature` / `switch.boiler_switch`.
