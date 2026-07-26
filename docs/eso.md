# ESO integracija (custom_components/eso)

Upstream: `algirdasc/hass-eso` (mūsų fork `celadondeep/hass-eso`;
PR #39 backfill, #40 stored sensorius — laukia maintainerio). Lokali
versija truputį diverguoja (LT atributai `menuo`/`serija`).

## Prisijungimas

- mano.eso.lt, Drupal; 2FA kodas el. paštu → IMAP (arunasziv@gmail.com).
- Sesija saugoma `eso_session.json`, bet ESO autologout ją numarina per
  kelias valandas — kasdienis importas beveik visada daro pilną login.
- **OTP švara:** panaudotas kodo laiškas trinamas iškart; po sėkmingo
  pilno prisijungimo papildomai iššluojami VISI likę kodų laiškai
  (trinami tik laiškai su kodo šablonu). Dėžutė svyruoja 0–1 laiško.
  Pamoka: pasenęs kodas dėžutėje = prisijungimo strigtis (nauji login'ai
  anuliuoja senus kodus).

## Kasdienis importas (5:10–6:40, atsitiktinis laikas)

1. Valandiniai P+ (importas) / P− (eksportas) → ilgalaikė statistika
   `eso:energy_consumed_220588` / `eso:energy_returned_220588`
   (istorija nuo 2026-04-01; backfill per `eso.import_now` su
   date_from/date_to, ~90 d. gabalais).
2. **Pasaugojimo banko serija** — suvartojimo forma su `stored_energy=1`
   (mėnesio rodinys): `sensor.eso_bankas_220588` = paskutinio UŽDARYTO
   mėnesio galo likutis (einamas mėnuo ESO serijoje visada 0).
3. **Planuojami atjungimai** — dashboardo blokas
   (`planned_disconnects_block`): `sensor.eso_atjungimai` (būsena =
   artimiausias langas / „nenumatoma", atributas `tekstas` = originalus
   bloko tekstas). Pranešimų dėžutės NESKAITOME (vartotojo sprendimas
   2026-07-18).

## Pasaugojimo bankas (packages/eso_bankas.yaml)

- Schema: eksportas → bankas, importas dengiamas 1:1; banko metai
  bal. 1 – kov. 31; **bankas nelenda į minusą** (deficitinis mėnuo
  nusausina iki 0 — patvirtinta 2026-04 faktu: −274 kWh nesikaupė).
- `eso_bankas_likutis` = oficialus ESO (uždaryto mėn.) + einamojo mėn.
  eksportas − importas (mėnesio SQL sensoriai) + rankinė korekcija.
- `eso_bankas_prognoze` — trajektorija iki kovo 31 su mėnesio grindimis;
  mėnesių exp/imp lentelės PRELIMINARIOS — mėnesiui užsidarius auditas
  keičia faktu (pakete IR dashboardo grafike — sinchroniškai!).
  2026-07 prognozė: deficitas ~1170 kWh nuo ~lapkričio → nudegimo
  rizikos nėra, kaupti agresyviai.
- `baterijos_ciklo_nuostolis` — ciklo kaina vs bankas 1:1 (~6 ct/kWh).

## Atjungimų rezervo grandinė (packages/eso_pranesimai.yaml)

1. Importas randa atjungimą dashboarde → `eso_planned_outage` įvykis
   (dedup per `eso_seen_messages.json` outage: raktus).
2. `eso_atjungimas_is_dashboardo`: langas → `input_datetime.eso_atjungimas_nuo/iki`
   + `input_boolean.eso_rezervo_planas` ON + notification (tik ateities datai).
3. Likus ≤14 val. → `storm_mode` ON (baterija atjungimo dienai kaupiaama pilna).
4. Langui praėjus +30 min → storm_mode ir planas OFF.
- Saugiklis: blokas ne tuščias, bet langas neatpažintas (užpildyto bloko
  markup dar nematytas!) → įspėjimo notification su tekstu; langą galima
  įvesti ranka — likusi grandinė veikia taip pat.
- Rankinis storm_mode be plano automatikos neliečiamas.

## Žinomi faktai / spąstai

- Backfill „Kita" periodo formos kelias — vienintelis istorinių valandinių
  duomenų šaltinis (savaitės rodinys visada rodo tik paskutines 7 d.).
- Statistikos sumos tęsiamos nuo paskutinio taško (60 d. lookback) — spragos
  užpildomos import_now su date_from/date_to.
- Eimo ESO paskyra NEpajungta — bankas/atjungimai tik Namų įvadui
  (obj. 220588, sutartis 18116704, objektas 35015580).
