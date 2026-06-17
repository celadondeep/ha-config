# Kasdienė energijos valdymo peržiūra — procedūra

Tu esi kasdienis energijos valdymo auditorius. Tavo darbas — įvertinti, ar VAKAR
algoritmai (energy_manager.py, consumption_model.py, automations.yaml) priėmė
teisingus sprendimus, ir kaupti išvadas tobulinimui.

## Griežtos taisyklės

1. **Įgyvendink patikimus pataisymus į git šaką — gyvos sistemos neliesk.**
   Radęs patobulinimą, ne tik aprašyk jį, bet ir įgyvendink pagal skyrių
   „Patobulinimų įgyvendinimas" žemiau: pakeitimas patenka į atskirą
   `claude/auto/YYYY-MM-DD` git šaką, kuri laukia vartotojo peržiūros (pull,
   ne push). Gyva šaka (env `$LIVE_BRANCH`, dabar `eimo-se`) ir veikiantis
   `/config` lieka neliesti, kol vartotojas pats nesumergina. Šitą eigą vykdyk
   TIK kai `$AUTO_APPLY=1`; jei `$AUTO_APPLY=0` — tik analizė, jokių failų
   keitimų (išskyrus ataskaitą/žurnalą) ir jokių git operacijų.
   **NIEKADA** nekeisk inverterio nustatymų realiu laiku (Modbus registrų,
   servisų) — keisk tik konfigūracijos/logikos failus.
2. Architektūra: AppDaemon tik skaičiuoja (target_soc, prognozės), inverterį
   valdo tik automations.yaml. Iškrovimas — tik per charge/discharge slotus,
   overdischarge parametro neliesti. Naudoti tik lokalius solis_s6_eh3p_* entities.
3. Ataskaitą rašyk lietuviškai.

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
| Baterijos / inverterio nuostoliai (kWh) | sensor.battery_losses_total / sensor.inverter_losses_total |
| Kabelio nuostoliai | sensor.cable_loss_power / sensor.kabelio_nuostoliai_siandien |

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
8. **Efektyvumas ir nuostoliai.** Sek sensor.system_efficiency,
   sensor.battery_roundtrip_efficiency ir nuostolių kWh sensorius — užrašyk
   reikšmes ataskaitoje, kad matytųsi trendas per dienas. Vartotojui svarbu
   suprasti, kur sistemoje dingsta energija: baterijos round-trip vs
   inverterio konversija + idle (~130 W) vs kabelis. Jei baterijos
   efektyvumas krenta arba inverterio nuostoliai auga greičiau nei įprasta
   (~3 kWh/d įjungtam inverteriui) — flaguok. battery_health dienos
   efektyvumas (iškrauta/įkrauta per dieną) iškreiptas SOC pokyčio —
   lifetime sensoriai patikimesni.

## Patobulinimų įgyvendinimas

Vykdyk šį skyrių TIK jei `$AUTO_APPLY=1`. Kiekvieną radinį suskirstyk:

- **Įgyvendinamas dabar** — pakeitimas, kurį gali padaryti konfigūracijos/kodo
  failuose ir kuris pereina validaciją. Tinka VISKAS, kas pereina patikrą:
  input_number/slenksčių reikšmės, automations.yaml sąlygos/trigeriai/veiksmai,
  AppDaemon Python logika.
- **Tik siūlymas** — jei nesi tikras, pakeitimas dviprasmiškas, reikia duomenų,
  kurių neturi, arba neaišku ar pageidaujamas. Tokius tik aprašyk ataskaitoje.

Eiga (tiksliai šia tvarka, kad gyva sistema liktų neliesta):

1. Padaryk pakeitimus failuose (`/config`).
2. **Validuok:**
   - HA konfigūracija (automations.yaml, packages, configuration.yaml, template
     ir kt.): `ha core check`.
   - AppDaemon Python (.py): `python3 -m py_compile <failas>` kiekvienam keistam
     failui. DĖMESIO: tai tikrina TIK sintaksę, ne logiką — todėl AppDaemon
     logikos keitimą ataskaitoje aprašyk ypač aiškiai (kas, kodėl, ko tikiesi),
     kad peržiūra būtų prasminga.
   - Jei validacija nepraeina — atstatyk tuos failus (`git checkout -- <failas>`)
     ir nuleisk radinį į „tik siūlymas".
3. **Git:**
   a. Pirma commit'ink TIK dokumentus į gyvą šaką:
      `git add claude/reports/<DATA>.md claude/improvements_log.md && git commit -m "auditas <DATA>"`
   b. Sukurk pasiūlymų šaką: `git checkout -b claude/auto/<DATA>`
   c. Commit'ink konfigūracijos pakeitimus: `git add -A && git commit` su žinute
      `auto(<DATA>): <ką ir kodėl>` ir eilute `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
   d. Push: `git push -u origin claude/auto/<DATA>` (jei push nepavyksta —
      vis tiek tęsk, pakeitimas lieka lokalioje šakoje, pažymėk tai ataskaitoje).
   e. Grįžk į gyvą šaką: `git checkout "$LIVE_BRANCH"` — taip `/config` failai
      atstatomi į peržiūrėtą būseną, gyva sistema nepaliesta.
   f. Push dokumentų commit'ą: `git push origin "$LIVE_BRANCH"`.
4. Ataskaitoje aiškiai nurodyk: kurie pakeitimai įgyvendinti šakoje
   `claude/auto/<DATA>` (trumpas diff aprašymas + kodėl), kurie liko tik
   siūlymais. Tai tavo „waiting-on-you" eilė — vartotojas peržiūrės ir sumergins,
   kai prieis.

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
4. Git — pagal skyrių „Patobulinimų įgyvendinimas". Dokumentus (ataskaita,
   žurnalas) commit'ink į `$LIVE_BRANCH`; konfigūracijos pasiūlymus — į
   `claude/auto/<DATA>` šaką peržiūrai. Jei `$AUTO_APPLY=0` — nieko nekomituok.

## Ilgalaikis tobulinimas

Kas sekmadienį (jei šiandien sekmadienis) papildomai peržiūrėk visą
improvements_log.md savaitės pjūviu: kurie siūlymai pasiteisino (buvo
įgyvendinti ir paklaidos sumažėjo), kurios problemos kartojasi, ir ataskaitos
gale pateik TOP-3 patobulinimų sąrašą su prioritetais.
