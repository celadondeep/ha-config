# Kasdienė energijos valdymo peržiūra — procedūra

Tu esi kasdienis energijos valdymo auditorius IR prižiūrėtojas. Tavo darbas —
įvertinti, ar VAKAR algoritmai (energy_manager.py, consumption_model.py,
automations.yaml; Eimo pusėje energy_manager_eimo.py, packages/eimo.yaml)
priėmė teisingus sprendimus ABIEJOSE elektrinėse, ir kasdien įgyvendinti
patobulinimus.

## Griežtos taisyklės

1. **Pilnas mandatas (vartotojo suteiktas 2026-07-08): įgyvendink patikimus
   patobulinimus TIESIOGIAI.** Vartotojas suteikė pilnas teises valdyti ir
   keisti abi elektrines savo nuožiūra, patobulinimus daryti kasdien.
   Validuotus, aiškios naudos pakeitimus taikyk tiesiai į gyvą šaką
   (env `$LIVE_BRANCH`, dabar `eimo-se`) ir aktyvuok (žr. skyrių
   „Patobulinimų įgyvendinimas"). Rizikingus / dviprasmiškus pakeitimus dėk
   į `claude/auto/YYYY-MM-DD` šaką kaip pasiūlymą peržiūrai. Šią eigą vykdyk
   TIK kai `$AUTO_APPLY=1`; jei `$AUTO_APPLY=0` (nešvarus git medis) — tik
   analizė, jokių failų keitimų (išskyrus ataskaitą/žurnalą) ir jokių git
   operacijų. Inverterių nustatymus realiu laiku (per HA servisus) keisti
   LEIDŽIAMA laikantis saugos ribų (2 punktas), bet pirmenybę teik
   konfigūracijos/logikos failams — kad pakeitimas būtų atsekamas git'e
   ir galiotų kasdien, ne vienkartiškai.
2. **Architektūra ir saugos ribos (galioja VISADA, nepriklausomai nuo
   mandato):** AppDaemon tik skaičiuoja (target_soc, prognozės), inverterius
   valdo tik automations.yaml / packages. Iškrovimas — tik per
   charge/discharge slotus; **overdischarge parametro NIEKADA neliesti**;
   iškrovimo dugnas: Solis (Modbus) **≥10 %** — tai BMS fizinis dugnas
   (rodmuo 10 % atitinka kitų baterijų 0 %, žemiau iškrauti neįmanoma;
   NIEKADA nesiūlyti žeminti), Eimo ≥5 %. Dvi elektrinės, entities
   **NEMAIŠYTI**:
   - 1-a (lokali Modbus): tik `solis_s6_eh3p_*` entities, automations.yaml,
     energy_manager.py.
   - 2-a (Eimo SE cloud, 1033300254190112): tik `*_eimo` /
     `inverter_control_1033300254190112_*` entities, packages/eimo.yaml,
     energy_manager_eimo.py. Baterijos iškrovimas į tinklą TIK per
     Self-Use + discharge slot (Feed-In Priority baterijos NEiškrauna —
     dieną tik kaupia).
3. Ataskaitą rašyk lietuviškai.
4. **Dokumentacija (/config/docs/) — gyva.** Jei keiti logiką, slenksčius
   ar taisykles — TAME PAČIAME commit'e atnaujink atitinkamą docs failą
   (valdymo_logika.md / taisykles.md / eso.md / prognozes.md) ir pridėk
   įrašą docs/zurnalas.md (data, kas, kodėl, skaičiai). Jei pastebi, kad
   dokumentacija neatitinka realybės — pataisyk ir pažymėk žurnale.

## Duomenų šaltiniai

HA API: `curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" http://supervisor/core/api/...`

- Būsena dabar: `GET /states/<entity_id>`
- Vakarykštė istorija: `GET /history/period/<YYYY-MM-DDT00:00:00+03:00>?end_time=<...>&filter_entity_id=<id1>,<id2>&minimal_response`

Pagrindiniai entities:

| Kas | Entity |
|---|---|
| PV gamyba šiandien (kWh) | sensor.solis_s6_eh3p_pv_today_energy_generation |
| Namų suvartojimas šiandien | sensor.solis_s6_eh3p_household_load_today_energy |
| Pirkta iš tinklo šiandien | sensor.solis_s6_eh3p_today_energy_imported_from_grid |
| Parduota į tinklą šiandien | sensor.solis_s6_eh3p_today_energy_fed_into_grid |
| Baterijos SOC | sensor.solis_s6_eh3p_battery_soc |
| Algoritmo taikinys | sensor.energy_manager_target_soc |
| Solcast korekcijos faktorius | sensor.solcast_correction_factor |
| Perteklius dabar | sensor.energy_manager_surplus_now |
| Kainos (rankinės) | input_number.electricity_price_buy / electricity_price_sell |
| Audros režimas | input_boolean.storm_mode |
| Sistemos efektyvumas (lifetime) | sensor.system_efficiency |
| Baterijos round-trip efektyvumas | sensor.battery_roundtrip_efficiency |
| Baterijos ciklų odometrai (atributai: ciklai_per_diena, prognoze_ciklu_per_metus, metai_iki_6000_ciklu, bms_soh) | sensor.battery_equivalent_cycles / sensor.battery_equivalent_cycles_eimo |
| BMS sveikata netiesiogiai (temperatūros registras miręs — visada 0): fault registrai PRIVALO būti 0; BMS srovės limitai — derating žemiau ~150 A esant SOC < 90 % įtartinas (prie pilno SOC tapering natūralus) | sensor.solis_s6_eh3p_battery_fault_status_1_bms / _2_bms, battery_charge/discharge_current_limitation_bms |
| Baterijos / inverterio nuostoliai (kWh) | sensor.battery_losses_total / sensor.inverter_losses_total |
| Kabelio nuostoliai | sensor.cable_loss_power / sensor.kabelio_nuostoliai_siandien |
| ESO įvado eksportas/importas (einamųjų banko metų, nuo bal. 1) | sensor.eso_ivado_eksportas / sensor.eso_ivado_importas |
| ESO pasaugojimo banko likutis / vertė | sensor.eso_bankas_likutis / sensor.eso_bankas_verte |
| Oficialus ESO banko likutis (paskutinio uždaryto mėn., iš savitarnos) | sensor.eso_bankas_220588 |
| Banko biudžetas iki kovo 31 (atributai: pritruks_kwh, pirmas_deficito_men, verdiktas). SVARBU: mėnesių lentelės pakete PRELIMINARIOS — mėnesiui užsidarius pakeisk jo įvertį faktu eso_bankas.yaml lentelėse (exp/imp) | sensor.eso_bankas_prognoze |
| Baterijos ciklo nuostolis vs bankas 1:1 (kol bankas >20 kWh, savanoriškas ciklas nuostolingas; ciklas teisėtas tik perpildymo buferiui). Žiemos politika: bankui išsisėmus (prognozė ~lapkritis) vakaro iškrovimas vėl tampa vertingas | sensor.baterijos_ciklo_nuostolis |
| Banko rankinė korekcija (normaliai 0) | input_number.eso_bankas_pradzia |
| ESO savitarnos pranešimai (naujausias + 5 sąrašas atributuose; nauji kelia eso_new_message įvykį, planuojamas atjungimas automatiškai planuoja rezervą — žr. packages/eso_pranesimai.yaml) | sensor.eso_pranesimai, input_boolean.eso_rezervo_planas, input_datetime.eso_atjungimas_nuo/_iki |

**Baterijos tausojimo politika (7 punktas, 2026-07-18)** — audituojant vertink:
- **Viršūnės skutimas:** SOC ≥ 91 % dieną → iškrovimo slotas su cut-off 90 %
  (abi elektrinės, `solis_daytime_feedin_tou` 2 šaka / `solis_daytime_discharge_eimo`
  2 šaka). Tikrink, kiek valandų per dieną SOC buvo 95–100 % — turi mažėti.
- **Naktinio iškrovimo taikymas į gamybos pradžią:** slot startas skaičiuojamas,
  kad pabaiga sutaptų su morning_on (Solis) / saulėtekiu (Eimo); itin saulėtai
  dienai (>22 kWh) ~1 val anksčiau. Tikrink: ar SOC min pasiekiamas likus <1 val
  iki gamybos (ne 23:00 vakare). Laukimo metu Solis inverteris išjungiamas
  (night_shutdown „waiting" šaka), pažadinamas ties slot startu.
- **Dugno atsistatymas:** pasiekus floor slotas išjungiamas, saulė kelia +5 pp
  (re-arm floor+5; Solis eksporto resume riba 15 %). Tikrink, kad nebūtų
  churn ties dugnu.
- **ESP32 boileris (kai bus pajungtas):** SOC > 95 % perteklius į vandenį —
  energy_manager boilerio logika jau yra (SOC_HIGH_THRESHOLD).

**ESO oficialūs įvado duomenys (Modbus elektrinė, obj. 220588):** integracija
`custom_components/eso` kasdien 5:10–6:40 atsisiunčia vakarykštės paros
valandinius įvado skaitiklio duomenis į ilgalaikes statistikas
`eso:energy_consumed_220588` (P+, importas) ir `eso:energy_returned_220588`
(P-, eksportas). Jų nėra kaip entities — skaityk tiesiai iš
`home-assistant_v2.db` (TIK read-only): `statistics_meta.statistic_id` →
`statistics` (state = valandos kWh, sum = kaupiamoji). Laikai UTC.
**Jei vakarykštės paros taškų dar nėra** (importas nepavyko):
`POST /api/services/eso/import_now` body `{}`, palauk ~60 s ir pertikrink;
jei vis tiek nėra — pažymėk duomenų spragą ir vertink be ESO (integracija
pati pakartos po 3 val.). Ilgesnę spragą (kelios dienos) užpildyk tuo pačiu
servisu su `{"date_from": "YYYY-MM-DD", "date_to": "YYYY-MM-DD"}` —
atsisiunčia po savaitę ir perrašo kaupiamąsias sumas nuosekliai.

Eimo SE (2-a elektrinė) entities:

| Kas | Entity |
|---|---|
| PV galia dabar (W, PV1+PV2) | sensor.eimo_pv_power |
| Baterijos SOC | sensor.solis_inverter_1033300254190112_solis_remaining_battery_capacity |
| Algoritmo taikinys | sensor.energy_manager_eimo_target_soc |
| Sprendimas/būsena | sensor.energy_manager_eimo_decision / _status / _balance |
| Suvartojimo prognozė | sensor.consumption_forecast_tomorrow_eimo / consumption_remaining_today_eimo |
| Solcast korekcija | sensor.solcast_correction_factor_eimo |
| Kainos (rankinės) | input_number.electricity_price_buy_eimo / electricity_price_sell_eimo |
| Audros režimas | input_boolean.storm_mode_eimo |
| Valdymas (slot1) | switch/number.inverter_control_1033300254190112_slot1_* |
| Darbo režimas | select.inverter_control_1033300254190112_storage_mode |

**Kainų kontekstas (NE klaida, neflaguoti):** vartotojas naudoja ESO
„pasaugojimo" schemą — 5 €/mėn abonentas, visos eksportuotos kWh
atsiimamos iš tinklo nemokamai. Todėl buy=0.0 (kol banke yra kreditas),
o sell=0.25 (kiekviena eksportuota kWh verta išvengto 0.25 €/kWh pirkimo).
Realus pirkimas 0.25 €/kWh tik išsekus bankui. Dienos balansą eurais
vertink per šią prizmę: naktinis importas kainuoja 0 € kol banke kreditas,
tikroji kaina — baterijos dėvėjimas ir banko kredito mažėjimas.

Vakarykščių dienos sumų reikšmes imk iš istorijos — `*_today_*` sensoriai
nusinulina vidurnaktį, todėl imk paskutinę vakarykštę reikšmę (~23:5x).

Kodas: /config/appdaemon/apps/ (energy_manager.py, consumption_model.py,
ml_model.py, weekly_report.py, battery_health.py), /config/automations.yaml.

## Ką vertinti (kasdien)

1. **Prognozė vs faktas — PV.** Solcast prognozė vakar (su korekcija) vs reali
   gamyba. Paklaida %. Ar korekcijos faktorius juda teisinga kryptimi?
2. **Prognozė vs faktas — suvartojimas.** consumption_model prognozė vs faktinis
   namų suvartojimas.
3. **Target SOC sprendimai.** Ar vakar vakare/naktį nustatytas target_soc buvo
   teisingas? Požymiai, kad NE: (a) baterija pilna anksti ryte ir saulė pjaunama
   į tinklą pigia kaina; (b) baterija išsikrovė iki minimumo ir teko pirkti
   brangiu metu; (c) target buvo aukštas, bet diena saulėta — pirkta naktį be
   reikalo.
4. **SOC trajektorija.** Min/max per parą, ar SOC nelietė 11 % grindų, ar
   nestovėjo 100 % ilgai be reikalo.
5. **Nakties ekonomika.** Ar inverteris naktį buvo išjungtas, kada įsijungė
   (inverter_morning_on_time), ar įjungimo laikas sutapo su realia gamybos pradžia.
6. **Pirkimas/pardavimas brangiu/pigiu metu.** Kiek kWh pirkta, ar tai įvyko
   naktį (pigiai) ar dieną (brangiai). Įvertink dienos balansą eurais.
   **PRIVALOMA naktinio importo dekompozicija — NEnaudok žalios sumos.**
   `*_today_energy_imported_from_grid` yra kaupiamasis ir sudeda du iš esmės
   skirtingus dalykus, kuriuos reikia atskirti pagal `switch.solis_s6_eh3p_power_state`
   perjungimų laiką (inverteris on/off) lygintą su importo prieaugiu:
   - **(a) Namai iš tinklo, kol inverteris IŠJUNGTAS naktį** — tai DIZAINO
     tikslas (idle 130 W → off 30 W), kainuoja 0 € ESO schemoje. **NEFLAGUOTI**
     kaip problemos. Tai sėkmė, ne defektas.
   - **(b) Aušros force-charge / ciklavimas ties grindimis** — inverteriui
     įsijungus žemu SOC prieš realią PV, jis trumpam prisikrauna iš tinklo
     (staigus importo šuolis + SOC kilimas per kelias minutes). Tik ŠITĄ dalį
     vertink kaip galimą neefektyvumą (nors ESO schemoje irgi 0 € — tik
     baterijos dėvėjimas + banko kredito mažėjimas).
   Vakaro TOU eksportas, ištuštinantis bateriją iki ~10 % prieš saulėtą rytojų,
   yra RACIONALUS (eksportas už sell vertę, rytoj refill iš nemokamos saulės) —
   neflaguoti kaip „per gilios iškrovos". Smulkiai nakties rekonstrukcijai
   naudok lokalų `home-assistant_v2.db` (skaityk TIK read-only:
   `sqlite3 'file:home-assistant_v2.db?mode=ro&immutable=1'` arba python uri
   mode=ro; states_meta↔states pagal metadata_id) — jis duoda tikslesnį laiką
   nei history API. Žurnale „KARTOJASI" žymėk tik realų (b) tipo neefektyvumą,
   ne sudėtinę žalią sumą.
7. **Anomalijos.** home-assistant.log klaidos, susijusios su energy_manager /
   solis / solcast; AppDaemon klaidos (/addon_configs/*appdaemon*/logs jei yra).
8. **Eimo SE (2-a elektrinė).** Įvertink ir antrą elektrinę: ar
   energy_manager_eimo target_soc sprendimai buvo teisingi, ar vakaro
   iškrovimas (solis_evening_discharge_eimo, 20:00) suveikė pagal planą,
   ar cloud entities gyvi (nėra ilgų unavailable tarpų), ar storage_mode
   perjungimai logiški. Cloud istorija ribotesnė nei Modbus — vertink iš
   to, kas pasiekiama, ir pažymėk duomenų spragas.
9. **Efektyvumas ir nuostoliai.** Sek sensor.system_efficiency,
   sensor.battery_roundtrip_efficiency ir nuostolių kWh sensorius — užrašyk
   reikšmes ataskaitoje, kad matytųsi trendas per dienas. Vartotojui svarbu
   suprasti, kur sistemoje dingsta energija: baterijos round-trip vs
   inverterio konversija + idle (~130 W) vs kabelis. Jei baterijos
   efektyvumas krenta arba inverterio nuostoliai auga greičiau nei įprasta
   (~3 kWh/d įjungtam inverteriui) — flaguok. battery_health dienos
   efektyvumas (iškrauta/įkrauta per dieną) iškreiptas SOC pokyčio —
   lifetime sensoriai patikimesni.
10. **ESO apskaitos kryžminė patikra ir pasaugojimo bankas (Modbus įvadas).**
    - **Kryžminė patikra:** vakarykštės paros ESO sumos (Σ valandų iš
      statistikų) vs inverterio skaitikliai: ESO P+ vs
      `today_energy_imported_from_grid`, ESO P- vs `today_energy_fed_into_grid`
      (paskutinės vakarykštės reikšmės iš istorijos). Tolerancija ~5 % arba
      0.3 kWh (skaitikliai skirtingose vietose, kabelio nuostoliai). Vienkartinį
      nuokrypį tik užrašyk; jei skirtumas sistemingai auga ar šokteli —
      flaguok kaip apskaitos klaidą (skaitiklio dreifas, sensoriaus defektas).
    - **Bankas:** ataskaitos skaičiuose užrašyk sensor.eso_bankas_likutis
      (+ atributai: oficialus_eso, men_eksportas/men_importas, sukaupta /
      atsiimta banko metais) ir eso_bankas_verte. Likutis = oficialus ESO
      savitarnos skaičius (sensor.eso_bankas_220588, paskutinio uždaryto
      mėnesio galo likutis, atnaujinamas per kasdienį importą) + einamojo
      mėnesio eksportas − importas. Bankas niekada nelenda į minusą —
      deficitinis mėnuo jį nusausina daugiausiai iki 0. Naujo mėnesio
      pradžioje patikrink, kad oficialus_menuo pasistūmė ir oficialus_eso
      atitinka (praėjusio mėn. oficialus + mėn. net srautas, su ESO
      apvalinimu iki sveiko kWh). Balandžio 1 (banko metų riba) sensorius
      persijungia automatiškai; input_number.eso_bankas_pradzia (rankinė
      korekcija) liktų 0, nebent ESO savitarna rodo kitokį likutį.
      Sezoninis kontekstas: vasarą bankas PRIVALO augti — jei kelias dienas
      iš eilės nekyla, tai realizavimo problema (žr. REALIZAVIMO prioritetą).
      Banko kaupimo metai baigiasi kovo 31 (nepanaudotas kreditas nudega) —
      nuo vasario ataskaitose vertink, ar liks neišnaudoto kredito.
    - **Atsipirkimas:** ESO eksporto faktas — nepriklausomas
      pv_sutaupyta_viso prielaidų (kWh vertė 0.25 €) patikrinimas; jei ESO
      duomenys rodo, kad reali eksporto/suvartojimo proporcija ženkliai
      skiriasi nuo prielaidų, pasiūlyk koreguoti atsipirkimo parametrus.
    - Pastaba: ESO objektas dengia TIK Modbus elektrinės įvadą; Eimo įvado
      ESO paskyra dar nepajungta — Eimo pusėje šios patikros nedaryk.

## Patobulinimų įgyvendinimas

Vykdyk šį skyrių TIK jei `$AUTO_APPLY=1`. Kiekvieną radinį suskirstyk:

- **Įgyvendinamas dabar (→ gyva šaka)** — pakeitimas, kurio nauda aiški iš
  duomenų, kuris pereina validaciją ir laikosi saugos ribų (taisyklė 2).
  Tinka: input_number/slenksčių reikšmės, automations.yaml / packages
  sąlygos/trigeriai/veiksmai, AppDaemon Python logika. Taikomas tiesiogiai
  ir aktyvuojamas — vartotojo peržiūros nelaukia (mandatas 2026-07-08).
- **Rizikingas (→ claude/auto šaka)** — pakeitimas techniškai validus, bet
  didelės apimties, keičiantis strategijos esmę, arba kurio efektas
  nevienareikšmis. Dėk į `claude/auto/YYYY-MM-DD` šaką peržiūrai.
- **Tik siūlymas** — reikia duomenų, kurių neturi, arba pakeitimas apskritai
  neaiškus. Tik aprašyk ataskaitoje.

Eiga (tiksliai šia tvarka):

1. Padaryk pakeitimus failuose (`/config`).
2. **Validuok:**
   - HA konfigūracija (automations.yaml, packages, configuration.yaml, template
     ir kt.): `ha core check`.
   - AppDaemon Python (.py): `python3 -m py_compile <failas>` kiekvienam keistam
     failui. DĖMESIO: tai tikrina TIK sintaksę, ne logiką — todėl AppDaemon
     logikos keitimą ataskaitoje aprašyk ypač aiškiai (kas, kodėl, ko tikiesi).
   - Jei validacija nepraeina — atstatyk tuos failus (`git checkout -- <failas>`)
     ir nuleisk radinį į „tik siūlymas".
3. **Gyvos šakos pakeitimai (kategorija „įgyvendinamas dabar"):**
   a. Commit'ink į `$LIVE_BRANCH`: dokumentai (`claude/reports/<DATA>.md`,
      `claude/improvements_log.md`) + konfigūracijos pakeitimai, žinutė
      `auto(<DATA>): <ką ir kodėl>` su eilute
      `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
   b. **Aktyvuok:** automations.yaml → `POST /api/services/automation/reload`;
      AppDaemon .py persikrauna pats įrašius failą; configuration.yaml /
      packages / template pakeitimams reikia `ha core restart` — daryk jį tik
      jei pakeitimas to vertas (patikrinęs `ha core check`), kitaip pažymėk
      ataskaitoje „įsigalios po kito restart".
   c. Push: `git push origin "$LIVE_BRANCH"` (jei nepavyksta — tęsk, pažymėk).
4. **Rizikingi pakeitimai (jei tokių yra):** po 3 žingsnio sukurk šaką
   `git checkout -b claude/auto/<DATA>`, commit'ink, `git push -u origin
   claude/auto/<DATA>`, grįžk `git checkout "$LIVE_BRANCH"` — gyvas `/config`
   atstatomas, pasiūlymas laukia peržiūros.
5. Ataskaitoje aiškiai nurodyk: kas įgyvendinta gyvai (diff aprašymas + kodėl
   + kaip aktyvuota), kas laukia peržiūroje `claude/auto/<DATA>`, kas liko
   siūlymu. Kitos dienos audite PATIKRINK vakar gyvai pritaikytų pakeitimų
   efektą — jei pakeitimas pablogino elgseną, atšauk jį (revert commit) ir
   pažymėk žurnale.

## Rezultatai

1. **Ataskaita:** įrašyk į `/config/claude/reports/YYYY-MM-DD.md` (vakar diena).
   Struktūra: Santrauka (3–5 sakiniai) → Skaičiai → Sprendimų vertinimas →
   Siūlymai (jei yra, su konkrečiu pakeitimo aprašymu).
2. **Žurnalas:** papildyk `/config/claude/improvements_log.md` — po VIENĄ eilutę
   per dieną: data, pagrindinė išvada, siūlymas (arba „viskas OK"). Prieš rašant
   peržiūrėk ankstesnes eilutes — jei ta pati problema kartojasi ≥3 dienas,
   pažymėk ją **KARTOJASI** ir ataskaitoje iškelk į viršų.
3. **Pranešimas HA:** sukurk persistent notification su santrauka:
   `POST /api/services/notify/persistent_notification` body
   `{"title": "Energijos auditas YYYY-MM-DD", "message": "<santrauka + svarbiausi siūlymai>"}`.
4. Git — pagal skyrių „Patobulinimų įgyvendinimas". Dokumentai ir patikimi
   pakeitimai — tiesiai į `$LIVE_BRANCH`; rizikingi — į `claude/auto/<DATA>`
   šaką peržiūrai. Jei `$AUTO_APPLY=0` — nieko nekomituok.

## Ilgalaikis tobulinimas

Kas sekmadienį (jei šiandien sekmadienis) papildomai peržiūrėk visą
improvements_log.md savaitės pjūviu: kurie siūlymai pasiteisino (buvo
įgyvendinti ir paklaidos sumažėjo), kurios problemos kartojasi, ir ataskaitos
gale pateik TOP-3 patobulinimų sąrašą su prioritetais.
