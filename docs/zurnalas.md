# Sprendimų žurnalas

Chronologinis svarbių pakeitimų ir atradimų sąrašas (naujausi viršuje).
Auditas ir sesijos pildo po kiekvieno reikšmingo pakeitimo: data, kas
pakeista, KODĖL, kokie skaičiai tai pagrindė.

## 2026-08-01 (auditas)

- **Banko likučio mėnesio-ribos artefaktas (atradimas, NE pataisa).**
  `eso_bankas_likutis` nukrito 350→4.3 kWh, kai `eso_bankas_220588.menuo`
  pasistūmė į 2026-07, o ESO savitarna liepos uždarymo likučio dar nepaskelbė
  (oficialus_eso=0). Formulė (oficialus + einamojo mėn. neto) todėl „prarado"
  ~382 kWh (birž. 269 + liepos neto +112.7; ESO liepa: exp 242.9 / imp 130.2).
  **Savaime pasitaiso** ESO paskelbus liepą; `eso/import_now` (08-02) dar
  nepadėjo. **Poveikio valdymui NĖRA** — likutis/ciklo_nuostolis/prognozė
  naudojami tik packages/eso_bankas.yaml, jokioje automatikoje/AppDaemon.
  Rankinė `eso_bankas_pradzia` korekcija NEDĖTA (ESO paskelbus → dvigubas
  skaičiavimas). Ateities auditams: šis kritimas kartosis KAS mėnesio pabaigą
  1–2 sav., kol ESO publikuoja — tai laukiama elgsena, ne defektas. Svarstytina
  atsparumo pataisa (statistikų fallback su mėnesio flooring) — peržiūrai.
- **Recorderio 145 val. spraga (07-26 22:00 → 08-01 23:23):** istorija
  neįrašinėta (HA veikė, dienos skaitikliai kaupė). 08-01 auditas rėmėsi tik
  paros sumomis + ESO statistikomis; vidurdienio trajektorija neprieinama.

## 2026-07-26

- **🔴 Naktinis iškrovimas ~5 naktis neveikė (cut-off min 12 %):** iškrovimo
  cut-off SOC registro MINIMUMAS inverteryje = 12 % (range 12–100). Automatikos
  (evening_discharge, tou_recalc) rašydavo target=10 (clamp buvo ≥5) → inverteris
  ATMETA rašymą <12 ir palieka SENĄ reikšmę (dienos viršūnės skutimo 80). SOC 66 <
  80 → inverteris laiko bateriją rezervu, namus maitina tinklas, į banką neeksportuoja.
  PATAISA: abiejų automatikų clamp `≥5` → `≥12`. Su cut-off=12 (+ slotą perjungus)
  baterija iškrovė 1191 W, į tinklą ~1 kW. Dieninė `feedin_tou` jau naudojo floor
  clamp ≥12 (nepaliesta). backup_soc=80 (EPS rezervas) NEkaltas — netrukdo tinklinei
  iškrovai. grid_peak_shaving derinant išjungtas (ne priežastis). Detaliau atmintyje.

## 2026-07-24

- **🔴 Dieninis inverterio išjunginėjimas (klaida):** `solis_low_soc_night_shutdown`
  dieninė šaka `soc<=12 and pv<load` debesuotą rytą (SOC 10, PV 290 W < apkrova
  1847 W) kas 15 min išjungdavo inverterį — vartotojas rankiniu būdu įjungdavo,
  ji vėl išjungdavo (07-24: on 08:09 → off 08:15 → on 08:50). Prarandama ryto PV,
  namai vien iš tinklo. Dieninė šaka PAŠALINTA — apsauga nuo iškrovos žemiau dugno
  jau užtikrinta overdischarge=11 % (BMS), inverterio išjungti tam nereikia.
  Liko tik naktinė churn apsauga (20:30–10:00 / SOC≤6). Atitinka 07-22 vartotojo
  prašymą („neiškraudinėti žemiau 11" = overdischarge, ne inverterio išjungimas).

- **🔴 Ryto įjungimas vėluodavo 2+ val.:** `get_morning_on_time` PV slenkstį
  (100 W) lygino su Solcast prognoze, PADAUGINTA iš `hourly_factor` korekcijos.
  Ryte faktorius nuslopindavo vertę, tad įjungimo laikas nusikeldavo (07-24
  išeidavo 08:14 vietoj ~06:00), o inverteris pramiegodavo silpną ryto saulę
  (Eimo, buvusi įjungta, tuo metu jau gamino ~270 W). Pataisyta: slenkstis
  lyginamas su **žalia** Solcast valandine prognoze (be faktoriaus). Šiandienos
  žalia prognozė 100 W kerta 06:30 (0,164 kW) → įjungimas 06:00 (−30 min
  atsarga). Abi elektrinės (energy_manager + energy_manager_eimo). Vartotojo
  taisyklė: įjungti kai prognozuojama PV > 100 W.
- **Naktinis iškrovimas link ryto — įskaičiuotas suvartojimas:** iškrovimo lango
  DYDIS dabar = (SOC−target) MINUS nakties suvartojimas iki ryto gamybos (naujas
  `sensor.energy_manager_cons_until_production`, iš valandinio vartojimo profilio
  + inverterio savivartos). Anksčiau `hours` skaičiuota lyg visą iškrovą darytų
  vien 1 kW eksportas — langas startuodavo per anksti ir baterija dugną pasiekdavo
  prieš aušrą (nereikalingas stovėjimas ties minimumu). Dabar langas startuoja
  vėliau, baterija dugną pasiekia ties gamybos pradžia → trumpiausias laikas ties
  dugnu. Tikslas: baterija kraštutinėse būsenose (100 % ir dugne) būna kuo
  trumpiau. Namai įdiegta; Eimo — analogiškai.
- **Dashbordai — vartojimo grafikų šlifavimas:** valandinis grafikas — legendoje
  `kWh`, tooltip tik valanda; savaitės grafikas — praėjusi pilna savaitė Pr→Sk
  (span isoWeek −7d, 167h langas), lietuviški dienų vardai po stulpeliais,
  plona vientisa vidurkio linija be markerių; pašalintos ikonos iš pavadinimų.

## 2026-07-23

- **🔴 Valandinis mokymasis niekada neveikė (4 vietose):** vartojimo modelis
  kaupia pagal savaitės dieną (VEIKIA) ir valandą, bet valandinis profilis buvo
  užstrigęs ties numatytuoju. Priežastis: AppDaemon get_history grąžina
  last_changed kaip datetime objektą, o kodas tikėjosi ISO teksto → parsinimas
  žlugdavo. Ta pati klaida 4 failuose (consumption_model + energy_manager, abi
  elektrinės — valandinis vartojimas IR valandinė Solcast korekcija). Pataisyta.
- **Auditas:** pašalinti likučiai (cloud automatika, Namų cloud_control),
  ištaisytos mirusios nuorodos (Eimo consumption_yesterday, weekly_report,
  battery_health), pašalintas battery_equivalent_cycles dublikatas. Sukurtas
  tests/valdymo_simuliacija.py (8 situacijos × 2 elektrinės — švaru).
- **✅ Valandinio mokymosi pataisa PATVIRTINTA gyvai:** pridėtas rankinio
  paleidimo įvykis (CONSUMPTION_MODEL_RUN / _EIMO) derinimui; paleista rankiniu
  būdu — abi elektrinės išmoko iš realios recorder istorijos (Namai 23 val.,
  Eimo 20 val., profile_days 0→). Iki tol abiejų valandinė forma buvo IDENTIŠKA
  (užstrigusi ties numatytuoju) — dabar SKIRTINGA (Namai: rytinė 7–8 val. +
  vakarinė 17–21 viršūnės; Eimo: 9 ir 14 val.). `update_model` pabaigoje dabar
  iškart kviečia `update_ha_sensors` — po naktinio 00:05 mokymosi profilio
  dashbordas atsinaujina be 30 min vėlavimo.
- **Dashbordai — vartojimo profilio vizualizacija** (abi elektrinės):
  „Vartojimas" rodinys su valandiniu ir savaitės dienos grafiku
  (sensor.consumption_profile / _eimo, ApexCharts data_generator).
- **Dashbordai — tinklo srauto grafikas** (abi elektrinės): valandinis importo
  vs eksporto stulpelinis (group_by diff 1h). Namai — ESO įvadas
  (sensor.eso_ivado_importas/eksportas); Eimo — inverterio metiniai skaitikliai
  (grid_energy_purchased / on_grid_energy; Eimo prie ESO neprijungta).

## 2026-07-22

- **🔴 KLAIDOS TAISYMAS — Modbus langai VEIKĖ (ne „negyvi"):** 07-21 klaidingai
  nuspręsta „Modbus TOU slotai negyvi" — skaitytas ne tas registras (33132
  būsena vietoj 43110 valdymo). Įrodyta: 07-19 23:00 naktį langas ON (cut-off
  20), Feed-in+TOU, baterija iškrovė 4.4 kW, į tinklą 1 kW; naktinio eksporto
  į banką 65 kWh birž.–07/20. Mano 07-21 pakeitimai (vakaro iškrova →Self-Use)
  SULAUŽĖ naktinį eksportą. ATKURTA veikianti Modbus langų logika
  (evening_discharge, tou_recalc, daytime_feedin_tou). Cloud valdymas pridėtas
  be reikalo — paliktas OFF. TOU būsenai tikrinti: 43110, ne 33132.

- **KLAIDOS TAISYMAS — Feed-in NEnukerpa:** 07-21 klaidingai nuspręsta „vien
  Self-Use" (suklaidintas stebėjimas). Gyvai paneigta 07-22: Feed-in Priority
  — PV 5455 W (pilna), baterija +4 kW, į tinklą −1 kW vienu metu. Grąžinta
  vartotojo logika: aukšta diena (prognozė > slenkstis) → Feed-in; nuosaiki →
  Self-Use (`solis_morning_mode`).
- **Pervadinimas:** „Šeškiniai SE" → **„Namai SE"** (įrenginys, integracijos
  įrašas, jutiklių pavadinimai, informacinė lenta). Objektų ID nekeisti.
- **Dugno ciklavimo apsauga** (vartotojo prašymu): baterija naktį/rytą
  cikluodavo 10–15 % ties dugnu kai saulės per mažai. Išplėsta churn apsauga —
  inverteris pailsi kai **SOC ≤ 12 % IR PV < namų apkrova** (bet kada, ne tik
  naktį); pažadina Eimo PV > 1200 W. `overdischarge` lieka 11 % (nepaliestas,
  vartotojo rule). Baterija nebekabo/nesiciklauja ties dugnu, kai negali krautis.
- **Kliento lango maketas** (paslaugos vizija): white-label elektrinės
  stebėsena + keli valdymo mygtukai (Artifact). HA nematomas.

## 2026-07-21

- **🔴 Modbus TOU slotai NEGYVI (atradimas):** Namų inverterio firmware
  atmeta TOU bitą (43110) — komandom rašo 3/66, nuskaito 1/64. Vadinasi visi
  grafiku valdomi eksporto/skutimo slotai per Modbus NEVEIKĖ. Sprendimas:
  pridėtas **SolisCloud valdymas Namams** (`solis_cloud_control`, SN
  ...110046) — cloud slotai veikia (patvirtinta: storage_mode→Self-Use
  pakeitė Modbus 43110). Padala: Modbus=telemetrija+režimas, cloud=slotai.
- **🔴 Feed-in Priority NUKERPA saulę (atradimas):** su ESO 1 kW eksporto riba
  (fiksuota, negalima pakelti) FiP nepilnai baterijai curtailina PV. Gyvai:
  PV 575 vietoj 5640 W, ~5 kW/s prarasta. **Sprendimas: dienos pagrindas
  VISADA Self-Use;** FiP pašalintas iš visų Namų aktyvių automatikų
  (morning_mode, evening_discharge, tou_recalc).
- **Skutimo slotas užšaldydavo bateriją (atradimas + taisymas):** iškrovimo
  slotas su cut-off 80 % veikia kaip rezervas — vakare PV nukritus baterija
  užšąla ties 80 %, namai iš tinklo. Pridėtas ATLEIDIMAS (Eimo): slotą
  išjungti kai aktyvus ir tinklas importuoja.
- **Sveikatos zona 20→30 %:** apatinė riba pakelta (vartotojo prašymas).
  Aptarta: su 1 kW riba ji „soft" — pasiduoda realizavimui, kad nenukirptų.
- **HA 2026.7 lūžiai (taisyta):** ryto inverterio įjungimo trigeris
  (`at: time.` domenas nebepriimamas → template); docs sidebar dashboard
  raktas be brūkšnelio (`dokumentacija`→`dokumentacija-docs`).
- **⏳ LAUKIA:** Namų eksporto/skutimo perrašymas ant cloud slotų
  (peak-shave + naktinis bankas). Atidėta dienai su stabiliu cloud.

## 2026-07-18

- **Sveikatos zona 20–80 %** (vartotojo tikslas): nuosaikią dieną
  (≤28/26 kWh) naktinis target ≥20, dienos skutimo lubos 80; aukštos
  gamybos dieną — pilnas diapazonas. BMS balansavimą prie 100 % atlieka
  piko dienos natūraliai.
- **Dinaminis FiP/Self-Use slenkstis**: laisva vieta + 0.5×vartojimas
  (tuščiam ≈22 kWh — sutampa su senu statiniu; pusiau pilnam ≈15).
  Prieš tai slenkstis nuleistas 22→10, galiausiai pakeistas formule.
- **PLAN_MARGIN 1.15 → 1.25** (vartotojas: „geriau daugiau vietos") —
  Solcast kuklina (korekcija +2.6 %, intraday 1.07–1.09, iki 128 % dienų).
- **Atsipirkimo auditas**: sutaupymas buvo pervertintas ~20 % (vertinta
  pagaminta, ne naudinga energija) — dabar gyvas naudingumo koef. ~0.80;
  Modbus starto data formulėse 04-01 → 05-09. Sutaupyta 1003→798 €.
- **ESO atjungimai — tik iš dashboardo bloko** (pranešimų dėžutės kelias
  pašalintas vartotojo sprendimu); rezervo grandinė: langas → planas →
  storm −14 val. → OFF po lango (+30 min); grandinė patikrinta simuliacija.
- **OTP švara**: po pilno login iššluojami visi likę kodų laiškai
  (rasta 13 susikaupusių; seni kodai kėlė login strigtis).
- **Baterijos tausojimo politika („7 punktas", vartotojo spec)**: viršūnės
  skutimas, naktinio iškrovimo pabaiga ties gamybos pradžia (Solis laukiant
  inverteris off + wake ties slot startu), dugno atsistatymas +5 pp,
  eksporto resume 30→15 %.
- **Dashboardai**: perbalansuotas Energijos view; „Audros/ESO rezervas" —
  viena kortelė su sąlyginėmis eilutėmis; header-toggle išjungti visur;
  sidebaras „Namai SE" / „Eimo SE".
- **Banko biudžetas**: eso_bankas_prognoze + trajektorijos grafikas —
  DEFICITAS ~1170 kWh nuo ~lapkričio (ne nudegimas!) → realizavimas
  pasitvirtina; baterijos_ciklo_nuostolis ~5.9 ct/kWh kol bankas gyvas.
- **Ciklų odometrai**: Solis 0.85 c/d (~19 m iki 6000), Eimo 0.43 c/d
  (~38 m). BMS temperatūros registras miręs — fault/limitų stebėjimas +
  Eimo temp alertas.
- **Valandinė Solcast korekcija** ir **vartojimo valandinio profilio
  mokymasis** įjungti (taikymas nuo ~07-25 / 07-19).

## 2026-07-17

- **ESO banko oficialus likutis** iš savitarnos (`stored_energy=1` serija):
  sensor.eso_bankas_220588. ATRADIMAS: bankas nelenda į minusą — metinė
  suma eksportas−importas nuvertino likutį ~274 kWh (29→303 kWh).
- **Tiksli Modbus paleidimo data**: 2026-05-09 ~13–15 val. (ESO valandinė
  istorija: 13:00 importas →0, 15:00 pirmas eksportas).
- **Orų kaupimas** vartojimo modeliuose (Open-Meteo t_mean/t_max);
  patvirtinta: šildymas ne elektrinis, kondicionierių nėra → orų
  koeficientas prognozei greičiausiai nereikalingas.
- Upstream PR #39 (backfill) ir #40 (stored sensorius) į algirdasc/hass-eso.
- Pervadinimai: įrenginys ir dashboardai → „Namai SE" / „Eimo SE".

## Iki 2026-07-17 (santrauka)

- 07-14: realizavimo kriterijus (battery_room_needed, CONS_BASE_KW=0.3),
  BMS dugno 10 % atradimas, dienos floor ≥12.
- 07-08: pilnas mandatas; dashboard pertvarka; banko paketas; audito
  procedūra su AUTO_APPLY.
- 07-01…07-07: naktinė ekonomika (idle 130 W → off 30 W), ryto įjungimas
  pagal Solcast, Eimo atskirimas (_eimo namespace), Eimo FiP neiškrauna
  baterijos atradimas.
## 2026-09-09 — Eimo SolisCloud Stage-1 ryšio atkūrimas

- Tik Eimo inverteriui `1033300254190112` startup'e apeinamas stringantis `/v1/api/inverterDetail` ir naudojamas paskutinis patvirtintas statinis inverterio profilis; kitiems inverteriams elgsena nepakeista.
- Eimo TOU V2 režimas fiksuojamas kaip `43605`, todėl po starto tiesiogiai naudojamas vienas `/v2/api/atReadBatch` kelias, kuris istoriniuose loguose buvo sėkmingas.
- Tik Eimo entry pirmo cloud refresh klaida nebeužlaiko config entry `setup_error`: naudojamas `coordinator.async_refresh()`, o entities lieka unavailable, kol nėra validžių duomenų. Kitiems inverteriams paliktas originalus privalomas first-refresh.
- Tik Eimo entry polling pakeistas iš 5 min į 1 min, o batch ir pavienių užklausų retry biudžetai apriboti iki 30 s; visiems kitiems `solis_cloud_control` inverteriams palikti originalūs 5 min / 180 s / 60 s nustatymai.
- `entity.available` papildomai saugo nuo `coordinator.data is None`.
- Git backup prieš pakeitimą: `backup/eimo-solis-stage1-20260909`. Pakeisti tik 4 failai po `custom_components/solis_cloud_control/`.
- Patikrinta Python sintaksė. Git `main` paruoštas; gyvam HA dar reikia, kad šie failai patektų į `/config` / `/homeassistant` ir būtų atliktas HA restartas bei patikrinti `atReadBatch` logai.

## 2026-09-09 — HA Admin skill/plugin ir Stage-1 CI

- Sukurtas repo-level `.agents/skills/home-assistant-admin` ir `AGENTS.md`, todėl atidarius `ha-config` Codex/Work aplinkoje HA darbo taisyklės yra pačiame repo.
- Tas pats skill laikomas ir `plugins/home-assistant-admin/skills/home-assistant-admin`; CI tikrina, kad abu variantai būtų identiški.
- Pluginas sąmoningai neturi `.mcp.json` su HA-MCP Connect URL: generated webhook URL yra kredencialas ir negali būti saugiai commitinamas į GitHub.
- `HA` custom app leidimai ChatGPT pusėje yra `Allow all actions`, tačiau šiame runtime HA tool namespace vis dar nepateiktas; todėl live HA deploy dar nelaikomas atliktu.
- Pridėtas `scripts/check_eimo_solis_stage1.sh` gyvai diagnostikai po restarto.
- Pridėtas `.github/workflows/ha-stage1-validation.yml`: tikrina 4 Stage-1 Python failus, shell skriptus, Eimo-only invariantus ir skill mirror.
- CI run #1 ir run #2 baigėsi `success`.


## 2026-09-09 — Dinaminis nakties valdymas

- Abiejų AppDaemon plannerių planas/targetas regeneruojamas kas 5 min; pridėti
  `planner_heartbeat`, `plan_generated_at`, `plan_valid_until`,
  `plan_trusted` ir atskiri `energy_manager*_night_plan` sensoriai.
- Namai: įgyvendintos fazės `EVENING_BOOST → SLEEP → DAWN_FINISH → DONE`.
  Vakaro fazė naudoja namų apkrovą + 1 kW eksporto kanalą, žemam targetui
  baterija vakare ruošiama iki ~20 % sleep SOC, tada inverteris OFF ir realus
  likutis užbaigiamas prieš PV pradžią.
- Nakties planas nebesiremia sena prielaida, kad visas `cons_until_production`
  iškraus bateriją, nors inverteris tuo metu gali būti OFF.
- Namų Modbus vykdymo minimumas suvienodintas su fiziniu TOU cut-off minimumu:
  12 %. Eimo cloud slot minimumas: 6 %.
- Namų `solis_tou_recalc_5min` tapo dinaminiu plano vykdytoju; senas 20:00
  vienkartinis `discharge_start` pašalintas. `HOLD` neutralizuoja eksportą ir
  palieka inverterį ON/Self-Use.
- Eimo slot1 nuo 19:30 iki 07:30 kas 5 min gali būti dinamiškai armuojamas /
  perarmuojamas / išjungiamas pagal planą; inverterio power-cycle nenaudojamas
  dėl cloud patikimumo.
- Ryto >100 W orientyrui naudojama žalia Solcast galia; dinaminio plano deadline
  nebeturi slenkančio `now+2 min` efekto.
- Dashboarduose rodomi fazė, target, sleep SOC, likusi kWh, dawn start,
  patikimumas ir plano atnaujinimo laikas.
- Rollback šakos:
  `backup/dynamic-night-plan-20260909` (Solis) ir
  `backup/dynamic-night-executor-20260909` (ha-config).
- CI: Solis Python `py_compile` + invariantai SUCCESS; ha-config YAML +
  valdymo simuliacija SUCCESS.

## 2026-09-09 — Minutės tikslumo ryto įjungimas

- Pašalintas senas fiksuotas 30 min `MORNING_ON_MARGIN_MIN`.
- Solcast `detailedForecast` 30 min vidutinės galios taškai interpretuojami
  intervalo viduryje; tarp gretimų taškų atliekama linijinė interpolacija.
- Inverterio ON timestamp = pirmoji pilna minutė, kai interpoliuota prognozė
  pasiekia `>=100 W`; laikas apvalinamas į viršų, kad inverteris nebūtų
  įjungtas prieš slenkstį.
- HA ryto automatika papildyta 1 min catch-up: jei Solcast atnaujinimas
  perstumia 100 W laiką į ką tik praėjusią minutę, inverteris įjungiamas per
  artimiausią minutę, o ne laukia seno timestamp trigerio.
- Rollback šakos:
  `backup/morning-100w-interpolation-20260909` ir
  `backup/morning-100w-executor-20260909`.
- CI testuoja konkrečius 50→150 W ir neapvalaus kirtimo scenarijus; SUCCESS.
