# Sprendimų žurnalas

Chronologinis svarbių pakeitimų ir atradimų sąrašas (naujausi viršuje).
Auditas ir sesijos pildo po kiekvieno reikšmingo pakeitimo: data, kas
pakeista, KODĖL, kokie skaičiai tai pagrindė.

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
  sidebaras „Šeškiniai SE" / „Eimo SE".
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
- Pervadinimai: įrenginys ir dashboardai → „Šeškiniai SE" / „Eimo SE".

## Iki 2026-07-17 (santrauka)

- 07-14: realizavimo kriterijus (battery_room_needed, CONS_BASE_KW=0.3),
  BMS dugno 10 % atradimas, dienos floor ≥12.
- 07-08: pilnas mandatas; dashboard pertvarka; banko paketas; audito
  procedūra su AUTO_APPLY.
- 07-01…07-07: naktinė ekonomika (idle 130 W → off 30 W), ryto įjungimas
  pagal Solcast, Eimo atskirimas (_eimo namespace), Eimo FiP neiškrauna
  baterijos atradimas.
