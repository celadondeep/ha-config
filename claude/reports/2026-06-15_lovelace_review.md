# Lovelace dashboard peržiūra — `energijos_valdymas.yaml`

> _Vienkartinė procedūros užduotis, atlikta 2026-06-15 (Opus 4.8). Tik analizė — YAML nekeistas
> (taisyklė №1). Žemiau išvados ir siūlomas pertvarkymas su konkrečiomis kortelėmis._

## Santrauka

Dashboard'as (2 puslapiai: **Energija**, **Analizė**; `type: sections`, `max_columns: 2`)
struktūriškai **sveikas**: visi **73 unikalūs entitetai egzistuoja**, visi 4 markdown `state_attr()`
atributai realiai grąžina reikšmes — **nė vienos sulūžusios nuorodos**. Išdėstymas logiškas (gyvi
rodmenys → valdikliai → grafikai). Pagrindiniai tobulinimai ne dėl klaidų, o dėl **nepanaudotų jau
skaičiuojamų duomenų**: 4 savaitės sensoriai ir mėnesio/metų skaitliukai niekur nerodomi, o didžiausia
ekonominė akloji zona — **nėra ESO kredito banko likučio**, nors visa „pasaugojimo" logika juo remiasi.

## 1. Entitetų integralumas — ✅ švaru

- 73/73 entitetai egzistuoja (kryžminta prieš 765 gyvus `entity_id`).
- Markdown „Naktinis planas 💤" atributai veikia: `kaina_ijungtas_eur_h`=0.105, `kaina_isjungtas_eur_h`=0.0576,
  `baterijos_kwh_verte`, `inverter_morning_on_time::laikas`=10:41. ✅

## 2. Dubliavimas — minimalus, daugiausia pateisinamas

| Kas | Kur | Vertinimas |
|---|---|---|
| `total_pv_power`, `household_load_power`, `battery_soc` | P1 „Dabartinė galia" glance + P1 24h grafikas | OK — momentinė reikšmė + trendas |
| `today_energy_consumption`, `_imported`, `_fed` | P2 „Šiandienos rezultatas" glance + P2 14d grafikas | OK — skaičius + trendas |
| **Inverterio temperatūra** | P1 „Energijos valdymas" (`energy_manager_inverter_temp`) **ir** P2 „Inverteris" + 48h grafikas (`solis_s6_eh3p_temperature`) | ⚠️ `energy_manager_inverter_temp` (57.8) = `solis_s6_eh3p_temperature` (57.8) — atrodo passthrough. Temp „Energijos valdymas" glance'e P1 dubliuoja P2; galima išimti iš P1 (vietoj jos – naudingesnis rodiklis). |

Išvada: tikro žalingo dubliavimo nėra; vienintelė reali redundancija — inverterio temp passthrough.

## 3. Trūkstama informacija — svarbiausia dalis

**a) Savaitės sensoriai skaičiuojami, bet NErodomi (greita nauda, naujų sensorių nereikia):**
- `sensor.savaites_pv_generacija`, `sensor.savaites_namu_suvartojimas`,
  `sensor.savaites_pirkimas_is_tinklo`, `sensor.savaites_pardavimas_i_tinkla`.

Siūloma kortelė (Analizė p., šalia „Šiandienos rezultatas"):
```yaml
- type: glance
  title: Savaitė
  entities:
    - { entity: sensor.savaites_pv_generacija, name: Saulė }
    - { entity: sensor.savaites_namu_suvartojimas, name: Suvartota }
    - { entity: sensor.savaites_pirkimas_is_tinklo, name: Pirkta }
    - { entity: sensor.savaites_pardavimas_i_tinkla, name: Parduota }
  show_state: true
```

**b) ESO kredito bankas — didžiausia ekonominė akloji zona.** Visa „pasaugojimo" schema (buy=0 €
kol banke kreditas) priklauso nuo likusio kredito, bet **tokio sensoriaus nėra** — neįmanoma matyti,
kiek kWh / € kredito liko ir kada teks pradėti realiai mokėti 0.25 €/kWh. Tai vienintelis dalykas,
reikalaujantis **naujo sensoriaus** (ne tik kortelės), todėl — tavo sprendimui:
  - paprasčiausia: `input_number.eso_kredito_bankas_kwh`, rankiniu būdu atnaujinamas iš ESO portalo;
  - arba kaupiamasis sensorius: Σ(eksportas) − Σ(importas) nuo schemos pradžios.

**c) Mėnesio / metų suvestinė (pasirinktinai).** Egzistuoja `pv_current_month_energy_generation`,
`pv_this_year_energy_generation`, `household_load_month/year_energy` — nė vienas nerodomas. Galima
pridėti „Mėnuo / Metai" glance Analizės puslapio apačioje.

**d) Naktinės SOC-11 apsaugos statusas.** Naujoji `automation.solis_soc_11_isjungti_inverteri_iki_ryto`
(svarbi, įgyvendinta 06-13) nematoma. „Automacijos būsena" kortelėje verta pridėti jos
`last-triggered`, kad matytųsi, ar/kada naktį suveikė.

## 4. Smulkūs nitpickai

- **Idle galios nesutapimas etiketėse:** P1 jungiklis pažymėtas „idle 130 W → 30 W", o „Naktinis
  planas" markdown ir energy_review procedūra mini ~140 W. Suvienodinti vieną skaičių.
- **`morning_on_time::laikas` dieną klaidina:** vidurdienį rodo 10:41 (į priekį žiūrinti reikšmė),
  nors „Ryto įjungimas" turėtų būti naktinis. Kosmetika — galima slėpti, kai saulė jau virš horizonto
  (`sun.sun` above_horizon).
- **`sensor.inverter_data_age` = `unavailable`, orphan** — dashboard jo nenaudoja (amžius
  skaičiuojamas JS'e iš `last_modbus_success`). Sensorius lieka kaboti „unavailable"; jei nereikalingas,
  verta pašalinti iš jo apibrėžimo vietos (template/konfige), kad neterštų entitetų sąrašo.
- **Fazių „Tinklas L1/L2/L3" (`meter_active_power_a/b/c`)** šiuo metu 0/0/0 (tinklo mainai ~0 — teisėta).
  Verta kada nors patikrinti esant aktyviam importui/eksportui, ar per-fazė pildosi (ne tik `_total`).

## 5. Siūlomas pertvarkymas (santrauka, prioritetai)

1. **[Greita, didelė nauda]** Pridėti „Savaitė" glance (3a) — duomenys jau skaičiuojami.
2. **[Svarbu, reikia sprendimo]** ESO kredito banko sensorius + kortelė (3b).
3. **[Vidutiniška]** „Mėnuo/Metai" glance (3c); SOC-11 apsaugos `last-triggered` (3d).
4. **[Kosmetika]** Suvienodinti idle W; slėpti `morning_on_time` dieną; išvalyti `inverter_data_age`
   orphan; apsvarstyti inverterio temp pašalinimą iš P1 (2 lentelė).

Nieko nepakeista — laukiu, kurį punktą norėsi įgyvendinti.
