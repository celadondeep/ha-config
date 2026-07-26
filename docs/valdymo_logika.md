# Valdymo logika — paros ciklas

> **Būsena: 2026-07-22.** Šis dokumentas atspindi TIKRĄ dabartinę logiką.
> Kas dar neįdiegta — pažymėta **⏳ LAUKIA**.

---

## 0. Pamatinis principas — režimo pasirinkimas

ESO leidžia atiduoti į tinklą **daugiausiai 1 kW** (fiksuota, negalima pakelti).
Dėl to režimas parenkamas pagal dienos gamybą:

- **Aukštos gamybos dieną (prognozė > slenkstis) → Feed-in Priority.** Nuo pat
  ryto ~1 kW keliauja į banką visą dieną, o baterija kraunasi iš likučio (>1 kW).
  Feed-in **NEnukerpa** — patikrinta gyvai 2026-07-22: PV 5455 W (pilna), baterija
  +4 kW, į tinklą −1 kW vienu metu. Daugiau eksporto ir mažiau nukirpimo nei
  Self-Use (kuris pripildo bateriją anksti, tada per piką nukerpa, nes atiduoti
  gali tik 1 kW).
- **Nuosaikią dieną (visa saulė tilptų, prognozė ≤ slenkstis) → Self-Use.**
  Saulė pirma į bateriją; perteklius virš pilnos ir taip eksportuojamas iki 1 kW.

> Pastaba: 2026-07-21 buvo klaidingai nuspręsta „VISADA Self-Use" (rėmėsi
> suklaidintu stebėjimu). Ištaisyta 2026-07-22 — grąžinta vartotojo logika.
> Slenkstis (morning_mode): `(100−SOC)×0.16 + likęs_vartojimas×0.5`.

---

## 1. Namai SE (Solis)

**Valdymo kanalai:** **viskas per lokalų Modbus** (`solis_s6_eh3p_*`) —
telemetrija, režimas IR laiko langai. Modbus TOU langai **VEIKIA**.

> **2026-07-22 pataisa:** 07-21 buvo klaidingai nuspręsta „Modbus slotai
> negyvi" — skaitytas ne tas registras. TOU BŪSENĄ rodo **43110**
> (`storage_control_switch_value`), NE 33132 (`storage_control_switching_value`
> — tik statusas). 43110=3 (Self-Use+TOU) → TOU bitas veikia. Naktinis
> eksportas į banką per Modbus langus VEIKĖ (65 kWh birž.–07/20). `solis_cloud_
> control` Namams pridėta be reikalo — nenaudoti valdymui (kad nekonfliktuotų).

### Kas VEIKIA dabar
- **Dienos režimas** (`solis_morning_mode` 06:00 pagal prognozę):
  - **Aukšta diena (prognozė > slenkstis) → Feed-in Priority** — nuo ryto
    ~1 kW į banką + baterija kraunasi iš likučio (Feed-in NEnukerpa,
    patikrinta 07-22).
  - **Nuosaiki diena (≤ slenkstis) → Self-Use** — saulė pirma į bateriją,
    perteklius virš pilnos automatiškai iki 1 kW į tinklą.
  - (2026-07-22 ištaisyta — 07-21 klaidingai buvo „vien Self-Use".)
- **Naktį** baterija natūraliai iškrauna namams iki dugno (10 %).
- **Inverterio įjungimas rytą** (`solis_morning_inverter_power_on`): pagal
  `inverter_morning_on_time` (Solcast gamybos pradžia −30 min), Eimo PV >200 W
  signalą arba 10:00 fallback. (Trigeris pataisytas 2026-07-20 dėl HA 2026.7.)
- **Dugno ciklavimo apsauga** (2026-07-22): inverteris pailsi (išjungiamas),
  kai **SOC ≤ 12 % IR PV nedengia namų** (saulės per mažai baterijai krautis)
  — bet kuriuo paros metu, ne tik naktį. Baterija ilsisi ant tinklo, nesiciklauja
  ties dugnu. Įsijungia saulei sustiprėjus (Eimo PV > 1200 W signalas). Naktinė
  churn juosta (10–15 %, 20:30–10:00) veikia kaip anksčiau. `overdischarge` lieka
  11 % (neliečiamas). Prideda idle 130 W → off 30 W ekonomiką.
- **Naktinis iškrovimas į banką** (`solis_evening_discharge` 20:00): jei SOC >
  target → Modbus iškrovos langas (21:00–07:30, cut-off = target, 150A,
  „Feed-in + TOU") — baterija iškrauna į tinklą 1 kW iki target. `tou_recalc`
  atnaujina cut-off kas 5 min, pasiekus tikslą išjungia. (Atkurta 2026-07-22.)
- **Dienos eksportas/skutimas** (`solis_daytime_feedin_tou`, kas 15 min):
  floor variantas (room_shortfall) ir viršūnės skutimas (80/90) per Modbus
  langus.
- **Apsauga:** SOC < 11 % → Self-Use.
- **AppDaemon** skaičiuoja `target_soc` ir `room_shortfall` (realizavimo
  kriterijus); Modbus langai juos ĮGYVENDINA (naktinė iškrova į target).

---

## 2. Eimo SE (cloud)

**Valdymo kanalas:** viskas per **SolisCloud** (`solis_cloud_control`,
`inverter_control_1033300254190112_*`). Cloud API lėtas ir rate-limituojamas
(rašoma tik kai reikšmė keičiasi); kartais meta „device timeout".
Eimo cloud **slotai VEIKIA** (skirtingai nei Namų Modbus).

- **Bazinis režimas: Self-Use.** (Eimo Feed-in Priority baterijos neiškrauna,
  todėl visas baterijos eksportas — tik per iškrovimo slotą.)
- **Diena** (`solis_daytime_discharge_eimo`, kas 15 min, 07:00–19:30):
  1. **Floor variantas** — `eimo_room_shortfall > 1 kWh`: slotas su
     cut-off = floor (6 %), perteklius į banką.
  2. **Viršūnės skutimas** — SOC ≥ lubos+1: slotas su cut-off = lubos
     (**80 %** nuosaikią / **90 %** aukštos gamybos dieną >26 kWh).
  3. **⚠️ Skutimo ATLEIDIMAS (2026-07-21):** kai skutimo slotas (cut-off ≥80)
     aktyvus IR **tinklas importuoja >200 W** (baterija užšalusi ties 80 %,
     namus dengia tinklas) — slotas išjungiamas, kad Self-Use baterija dengtų
     namus. Re-armuoja tik saulei vėl pakėlus SOC ≥ lubos+1.
  4. **Dugno atsistatymas / perteklius dingo** → slotas OFF, kaupiama.
- **20:00** vakaro iškrovimas: slotas su cut-off = `target_soc` (clamp ≥6),
  startas taikomas į saulėtekį.
- **20:05–07:00** recalc kas 5 min.
- Naktinio inverterio išjungimo nėra (cloud valdymu neįmanoma).

---

## 3. Sveikatos zona (abi elektrinės)

Nuosaikią dieną kaupiklį laikyti **30–80 % SOC** ruože (LFP tausojimas):
- **Apatinė 30 %** — `HEALTH_SOC_MIN = 30` (energy_manager*.py). Naktinis
  target ne žemiau 30 %.
- **Viršutinė 80 %** — per skutimo slotą (`shave_cutoff`).
- **Išimtis:** kai koreguota dienos gamyba > `BIG_DAY_KWH` (Solis 28 / Eimo 26
  kWh) — zona NEGALIOJA, naudojamas pilnas diapazonas (realizavimas svarbiau).

> **Su 1 kW eksporto riba apatinė riba yra „soft":** laikoma tik kai nemokama
> (debesuota rytdiena); saulėtą rytdieną, kai 30 % ribos laikymasis nukirptų
> saulę, ji pasiduoda realizavimui. **Namuose zona kol kas latentu** —
> įsigalios su cloud-slotais. Eimo — veikia.

---

## 4. Audros / ESO rezervo režimas (abi atskirai)

`input_boolean.storm_mode` / `storm_mode_eimo` → momentinis pritaikymas:
eksportas STOP, visa saulė į bateriją, baterija namams neiškraunama,
vakaro logika target = 100. Automatinis planavimas ESO atjungimams — žr.
`eso.md`.

---

## 5. Boileris (ESP32 — dar nepajungtas)

Logika paruošta `energy_manager`: strateginis leidimas pagal balansą,
taktinis pagal perteklių (SURPLUS_MIN 0.3 kW), SOC slenksčiai. Pajungus
reikės įrašyti tikrus entity ID.
