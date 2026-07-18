# Taisyklės ir saugos ribos

## Saugos ribos — galioja VISADA, nepriklausomai nuo mandato

1. **Overdischarge parametro NIEKADA neliesti.** Iškrovimas valdomas tik
   per charge/discharge slotus (vartotojo taisyklė nuo pat pradžių).
2. **SOC dugnai:** Solis (Modbus) **≥ 10 %** — tai FIZINIS BMS dugnas
   (rodmuo 10 % ≈ tikras 0 %, žemiau iškrauti neįmanoma; NIEKADA nesiūlyti
   žeminti; nuo 2026-07-14). Eimo **≥ 5 %** (slot cut-off min 6, dienos
   floor ≥ 6, Solis dienos floor ≥ 12 — inverteris atmeta žemesnį įrašą).
3. **Dviejų elektrinių entities nemaišyti** (žr. architektura.md).
4. **Audros/ESO režimas = rezervas:** visa saulė į bateriją, namai iš
   tinklo, baterija neiškraunama. Tai charge-slot mechanizmas, ne paprastas
   Self-Use.

## Vartotojo mandatas ir stilius

- **Pilnas mandatas (2026-07-08):** patikimi patobulinimai taikomi tiesiai
  ir aktyvuojami be peržiūros laukimo; rizikingi — į `claude/auto/<data>`
  šaką. Saugos ribos mandato neapima.
- **Investicijos sumos** (`input_number.pv_investicija`) programiškai
  nekeisti — pildo vartotojas.
- **input_number.eso_bankas_pradzia** — tik rankinei korekcijai, normaliai 0.

## Vartotojo energetikos principai (chronologiškai)

1. **Realizavimas svarbiau už target SOC** (2026-07-14): visa PV turi būti
   realizuota — bazinė apkrova (CONS_BASE_KW=0.3, ne prognozės vidurkis) +
   1 kW eksportas + baterijos vieta. Vartojimo prognozė plane neužskaitoma
   (tik bonusas). Nukirpta kWh prarandama 100 %, per didelė vieta kainuoja
   tik ~6–8 ct/kWh round-trip.
2. **Daugiau vietos geriau nei mažiau** (2026-07-18): PLAN_MARGIN = 1.25 —
   Solcast sistemingai kuklina.
3. **Eksportas nuo pirmų vatų** (2026-07-18): FiP — numatytasis Solis dienos
   režimas; Self-Use tik kai visa diena tilptų į laisvą baterijos vietą +
   namus be eksporto (dinaminis slenkstis pagal SOC).
4. **Sveikatos zona 20–80 %** (2026-07-18): nuosaikią dieną (koreguota
   prognozė ≤ 28 kWh Solis / ≤ 26 Eimo) kaupiklis 20–80 % ruože; aukštos
   gamybos dieną — pilnas diapazonas nuo dugno iki 100 (realizavimas
   svarbiau).
5. **Baterijos tausojimas** (2026-07-18, „7 punktas"): viršūnės skutimas
   (80/90 cut-off), naktinio iškrovimo pabaiga taikoma į gamybos pradžią,
   dugno atsistatymas +5 pp prieš eksporto atnaujinimą.
6. **Surplus be namų vartojimo:** surplus = pv_liko − baterijos_vieta;
   vartojimo nario negrąžinti. Sloto eksportas ~1 kW ≈ 1 kWh/val.

## UI / komunikacijos taisyklės

- **Entities kortelėse visada `show_header_toggle: false`** — jokio
  jungiklio prie antraštės (2026-07-18).
- Vieši PR (upstream) — be „Generated with Claude Code" atribucijos.
- Ataskaitos ir pranešimai — lietuviškai.
- Markdown kortelės ikonų nespalvina (temos overrides) — spalvoms naudoti
  button-card.

## ESO ekonomika (kontekstas sprendimams)

- Pasaugojimo schema: eksportas → bankas, importas dengiamas 1:1;
  buy=0.0 / sell=0.25 input_number'iuose — SĄMONINGA, neflaguoti.
  Mokestis 10 €/mėn (2 obj. × 5 €). Banko metai bal. 1 – kov. 31,
  nepanaudota nudega; **bankas nelenda į minusą** (mėnesio grindys 0).
- Kol bankas > ~20 kWh: savanoriškas baterijos ciklas nuostolingas
  (~6 ct/kWh) — teisėtas tik kaip 1 kW eksporto lubų perpildymo buferis.
  Bankui išsisėmus (prognozė ~lapkritis) ciklai vėl vertingi.
