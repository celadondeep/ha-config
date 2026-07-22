# Prognozės ir modeliai

## Gamybos prognozė (Solcast)

- Viena Solcast svetainė („seskiniu_2"), kalibruota Šeškinių stogui;
  Eimo naudoja tą pačią prognozę × savo korekcijos koeficientą.
- **Globali korekcija** (EMA α=0.2, 23:50, ribos 0.7–1.3): faktas/prognozė
  santykis. Būsena: `forecast_correction[_eimo].json`, sensoriai
  `solcast_correction_factor[_eimo]`. ~1.03 Solis / ~0.90 Eimo.
- **Valandinė korekcija** (nuo 2026-07-17): 04:40 dienos prognozės
  snapshot (vakare Solcast jau prisitaikęs — mokytis reikia iš rytinės),
  23:50 lyginama su pv_today valandinėmis deltomis (get_history), EMA
  per valandą, ribos 0.4–1.6. TAIKOMA tik sukaupus 7 paras (~2026-07-25);
  iki tol — globalus koeficientas. Naudojama: likusios dienos/rytojaus
  sumos, battery_room_needed per-periodui, ryto įjungimo laikas.
- **Intradienos santykis** (`solcast_intraday_ratio[_eimo]`): šios dienos
  faktas vs prognozė iki šio momento; plane tik didina (max(x,1)).
- **PLAN_MARGIN 1.25** — visur, kur skaičiuojama vieta (Solcast kuklina;
  nukirpimas kainuoja 100 %, per didelė vieta ~6–8 ct/kWh).
- Planuota (~nuo 2026-07-25): Open-Meteo radiacijos ensemble + clear-sky
  diagnostika (žr. atmintį plan-solcast-radiation-clearsky).

## Vartojimo modelis (consumption_model[_eimo].py)

- Statistinis: paros bazė (mediana/EMA) × savaitės dienos koef. (išmokti)
  × sezono koef. (kol kas fiksuoti: žiema 1.35 — ĮTARTINAI didelis be
  elektrinio šildymo, auditas tikslins rudenį).
- **Valandinis profilis** — nuo 2026-07-18 mokosi iš vakardienos
  kumuliacinių deltų (EMA α=0.1, normalizuotas, ≥20 val. ir ≥1 kWh
  apsaugos). Solis šaltinis: today_energy_consumption; Eimo:
  eimo_house_energy (sukurtas 07-17, mokymasis nuo 07-19).
- **Orai:** kas naktį prie istorijos rašomi t_mean/t_max (Open-Meteo, be
  rakto; Šeškiniai 54.456/23.024, Gražiškiai 54.468/22.921). Prognozė
  temperatūros NENAUDOJA — namuose ne elektrinis šildymas ir nėra
  kondicionierių (vasaros koreliacija +0.1…+0.36 = triukšmas); įjungti
  tik jei šildymo sezonas parodys realų signalą.
- Istorija: 120 parų (HISTORY_MAX_DAYS), faile `consumption_model*.json`.
- Publikuoja: consumption_forecast_tomorrow[_eimo],
  consumption_remaining_today[_eimo], consumption_daily_avg[_eimo].

## Faktai kalibravimui

- Namų bazinis vartojimas ~0.3–0.4 kW (balandis = grynas „iki PV" mėnuo:
  7–14 kWh/parą) — CONS_BASE_KW=0.3 patvirtintas.
- Paros gamybos maksimumai (2026 birž.–liep.): Šeškiniai 37.8 kWh,
  Eimo 32.8 kWh (Eimo plokščias 32.8 kelias dienas — įtariamas inverterio
  AC ribos apkarpymas, netikrinta).
- Metinė gamyba ~11 000 kWh abi kartu (Modbus 54 % / Eimo 46 %).
- Sistemos naudingumo koeficientas (naudinga/pagaminta) ~0.80 — naudojamas
  atsipirkimo skaičiavime (gyvas, iš lifetime skaitliukų).
