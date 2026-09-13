# Eimo duomenų „kadrai“ ir komandų laiko ribos

Patikra: 2026-09-13. Visi žmogui pateikti laikai — Europe/Vilnius.

## Išvada

Komandoms nenaudoti fiksuotų 00–05, 05–10 min. langų ir neperstumti
leidimo rašyti pagal telemetrijos atėjimą. Naudoti atskirus terminus:

- Skaitymas tam pačiam API adresui / įrenginiui: ankstesnio tinklo bandymo
  pabaiga + bent 300 s, įskaitant klaidą. Ilgesnė klaidos pauzė turi pirmenybę.
- Įrašas: ankstesnio įrašo bandymo pabaiga + bent 360 s **ir** vėlesnis
  tikslą atitinkantis registrų skaitymas. Vien sėkminga HTTP būsena ar naujas
  telemetrijos matavimas nepatvirtina komandos.
- Matavimo laikas reikalingas šviežumui, o ne valdymo laikmačiui. Ankstyvi,
  pavėlavę ir pasikartojantys matavimai laikmačio neatidaro ir nepradeda iš naujo.
- Ilga pauzė nekaupia „nepanaudotų komandų kreditų“: atstačius ryšį nėra
  pasivijimo serijos. Galioja tik naujausias dar aktualus planas.

Pavyzdys: įrašas baigtas 12:02:40. Iki 12:08:40 kitas įrašas negalimas,
nesvarbu, ar telemetrija atėjo 12:04, 12:05 ar 12:07. Jei tikras komandą
patvirtinantis skaitymas gaunamas 12:09:15, naujas įrašas galimas tik tada.
Naujos komandos terminas skaičiuojamas nuo jos pačios tinklo bandymo pabaigos.

## Istoriniai duomenys

Analizuotas `solis_timestamp_measurements_received` sensorius nuo rugsėjo
11 d. 21:00 iki rugsėjo 13 d. 09:22:35: 374 istorijos įrašai, 363 skirtingi
skaitiniai matavimo laikai. Pradinis lango ribos įrašas ir nepasikeitę
gretimi matavimo laikai neįtraukti į intervalų statistiką. Tarpai apima
skirtingas integracijos versijas, sutrikimus bei perkrovimus; jų negalima
visų priskirti naujai versijai.

| Dydis | Mediana | Mažiausias | Didžiausias |
|---|---:|---:|---:|
| Tarpas tarp šaltinio matavimo laikų | 300,03 s | 246,50 s | 2399,66 s |
| Tarpas tarp jų atsiradimo HA | 306,44 s | 183,81 s | 2493,71 s |
| Matavimo amžius gavimo HA momentu | 86,26 s | 5,18 s | 514,66 s |

Atgal grįžtančių matavimo laikų šioje imtyje nerasta. Tačiau jų fazė
nėra nekintama: rugsėjo 12 d. 23:02:29,778 sekė 23:06:36,473 — tik
246,695 s tarpas. Fiksuoto debesijos „kadro numerio“ iš HA gavimo laiko
patikimai nustatyti negalima.

Nuoseklus 300 s laukimas po atsakymo šiek tiek atsilieka nuo nominalaus
300 s matavimų ritmo, nes prisideda HTTP trukmė. Tai sąmoningas apkrovos
ribojimo kompromisas. Kito bandymo negreitinti vien norint pasivyti fazę.

## Gyvas 4.2.0 patikrinimas

Nuo 03:03 iki 09:20 žurnalo imtyje buvo šeši `/control` įrašai.
Didžiausias įrašų skaičius bet kuriame slenkančiame 300 s lange — **1**.
Mažiausias tarpas nuo ankstesnio įrašo pabaigos iki kito HTTP pradžios —
apie **366,96 s** (trukmės žurnale apvalintos iki šimtųjų).

Vieno kliento paleidimo ribose mažiausi tokie skaitymo tarpai:
`inverterDetail` 302,00 s, `stationDetail` 302,35 s, `atReadBatch` 303,44 s.
07:00:32 užbaigtas ON įrašas perskaitytas 07:06:37, tik po to prasidėjo
režimo įrašas. Nakties OFF įrašas 03:09:03 perskaitytas 03:15:05.

09:20:31 užbaigta `stationDetail` timeout klaida įjungė pauzę iki
09:25:31. 09:26:31 monitorius vėl rodė `healthy`, 193 sėkmės / 195
užklausos nuo paskutinio kliento paleidimo. Tai gyvas atsistatymo be
laiko rašymo ar aklo komandos kartojimo pavyzdys.

## Rasta išimtis ir 4.2.1 pataisa

03:55 perkrovimas sukūrė naują API klientą. Tarp ankstesnio ir naujo
kliento `inverterDetail` bandymų tebuvo 50,864 s, `atReadBatch` — 49,939 s.
4.2.0 skaitymų ribotuvas buvo tik atmintyje; tai tikra perkrovimo spraga,
ne duomenų fazės pasislinkimas. Išsaugota įrašų eilė 360 s ribos neprarado.

4.2.1 prideda bent 300 s tinklo tylos po naujo kliento sukūrimo.
Pradinis aptikimas tiesiog suplanuojamas vėliau, be HTTP bandymų serijos.
Patvirtinimo skaitymas taip pat tikrina monotoninį įrašo laukimo terminą,
kad sieninio laikrodžio šuolis pirmyn neleistų ankstyvo patvirtinimo.

43 regresiniai testai praėjo. Nauji atvejai tikrina ankstyvus, pavėlavusius
ir pasikartojančius matavimus, vėlyvą patvirtinimą be „kreditų“, pilną
300 s pradinę tylą ir laikrodžio šuolį prieš patvirtinimą. Tai nėra
ilgalaikio SolisCloud pasiekiamumo garantija.

**Gyvas 4.2.1 įrodymas:** klientas pradėtas 09:33:24,499, pirmas
HTTP bandymas pradėtas apie 09:38:24,510 — praėjus 300,01 s. Iki
09:39:21 užbaigti penki pradiniai kreipiniai, visi sėkmingi, įrašų — 0.
Monitorius `healthy`. 69 integracijos, HA paketo / skydelio ir AppDaemon
šaltinių failų SHA256 sutapo su saugomu kontroliniu tašku.

## Eksploatavimo būsena

Eimo automatinis vykdytojas buvo įjungtas 03:09, 09:03:07 išjungtas,
o 09:31:52 vėl įjungtas. Pastarųjų dviejų pakeitimų ši kadrų patikra
nesiuntė. Per 4.2.1 diegimą išsaugota vėliausia gyva nuostata; patikra
neperrašo lygiagrečiai pakeisto vykdytojo pasirinkimo.

09:46 LT baigiamoji patikra: API `healthy`, eilė `idle`, planuotojas ir
vykdytojas `ok`, vykdytojas įjungtas, telemetrija šviežia. Aštuonios
užklausos po paleidimo sėkmingos, nereikalingų valdymo įrašų — 0.
[GitHub patikros](https://github.com/celadondeep/ha-config/actions/runs/34743489726)
praėjo: 43 regresijos, Python, YAML, skriptų ir valdymo simuliacijos patikros.
Integracijos / HA kodas: `2327c56339cb9fa15311896085f100c8a9344771`;
AppDaemon kontrolinis taškas: `8a0d41ad20713a676275d373d67dc97fb0c668ab`.
