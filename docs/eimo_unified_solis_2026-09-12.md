# Eimo: viena Solis integracija

2026-09-12. Bazė: `hultenvp/solis-sensor` 4.0.1, commit
`6e360a073b8276bfa3140f003e9c0eeb3d10f63c`. Pritaikyta versija: **4.2.1**,
įdiegta 2026-09-13 (Lietuvos laiku).

## Paskirtis

Eimo telemetrija ir valdymas sujungti į `solis`. Atskira
`solis_cloud_control` konfigūracijos įrašas pašalintas, jos kodas iš aktyvaus
`custom_components` perkeltas į atsarginę kopiją. Senas rugsėjo 11 d.
Stage-1 diegimo planas nebetaikomas šiai migracijai.

Profilis `single_slot_control` įjungtas tik Eimo. Namų `solis_modbus`
valdymo logika šia migracija nekeičiama.

## Komandų tvarka

- Telemetrijos intervalas: ne trumpesnis kaip 300 s nuo užklausos pabaigos.
  Pasikartojantis senas duomenų laikas nelaikomas nauja telemetrija.
- Vienas registrų paketo skaitymo bandymas ne dažniau kaip kas 300 s;
  riba galioja ir po klaidos, ir priverstiniam patvirtinimo skaitymui.
- Kitas įrašas galimas tik praėjus bent 360 s nuo ankstesnio tinklo
  bandymo pabaigos **ir** vėliau perskaičius tikrą, tikslą atitinkančią būseną.
- API priėmimas nėra įvykdymo patvirtinimas. Valdymo objektai rodo
  perskaitytas reikšmes; pageidaujamas nustatymas pateikiamas atskirai.
- Neaiškaus rezultato įrašai automatiškai nekartojami. `not_confirmed`
  sustabdo visą įrenginio įrašų eilę. `Clear Pending Commands` leidžiamas
  tik po 6 min. ir naujo skaitymo, paliekant likusį laiko ribojimą.
- Laukiantis automatikos planas pakeičiamas naujesniu, nekaupiamas.
  Jo galiojimas 180 s; HA vykdytojas atnaujina norimą planą kas minutę.
- Aktyvi komanda išsaugoma prieš HTTP užklausą. Po perkrovimo ji
  tikrinama, tačiau laukiantys planai automatiškai neatkuriami.
- Atskirai nuo eilės HTTP kliento ribotuvas užtikrina 300 s intervalą
  tam pačiam skaitymo adresui ir įrenginiui bei 360 s tarp įrašų.
  Bendras kliento užraktas leidžia tik vieną HTTP užklausą vienu metu.
- Nuo 4.2.1 po paleidimo / perkrovimo taikoma 300 s pradinė tinklo tyla:
  ankstesnio kliento skaitymų ribos negalima apeiti sukuriant naują klientą.
  Aptikimas suplanuojamas pauzės pabaigai, nekartojant nesėkmingų HTTP bandymų.
  Sensorių inicializacija dėl to po perkrovimo gali užtrukti apie 10 min.
- Po klaidų daroma 300, 600, vėliau iki 1200 s pauzė. Pasikartojančios
  to paties API adreso klaidos neprarandamos vien todėl, kad kitas adresas
  atsakė sėkmingai. Prieš atnaujinant įrašus būtinas sėkmingas skaitymas.
  Inverterio laikas kaip ryšio „ping“ nerašomas.
- Vietoje užblokuota užklausa nelaikoma išsiųsta komanda. Nutrūkęs eilės
  darbuotojas atkuriamas per kitą apklausos ciklą; išsaugota neaiški komanda
  patikrinama be aklo pakartotinio įrašymo.
- Keičiant aktyvaus sloto parametrus, pirmiausia slotas sustabdomas.
  Automatika jį įjungia po nustatymų patvirtinimo, jeigu to vis dar
  reikalauja naujausias planas. Rankiniu būdu keičiant aktyvų slotą,
  užbaigus nustatymus jį reikia vėl įjungti.

## Palikti valdikliai

| Grupė | Valdikliai |
|---|---|
| Pagrindinis valdymas | Inverter On/Off, Storage Mode |
| Režimai | Self-Use, Feed-In Priority, Off-Grid |
| Leidimai | Allow Export, Allow Grid Charging, Battery Reserve, Grid Peak Shaving |
| Baterija | Force Charge, Over Discharge, Recovery, Reserve, Max Charge SOC; Max Charge ir Max Discharge Current |
| Galia ir laikas | Max Export Power, Max Output Power, Export Calibration, Inverter Time |
| Įkrovimas | Vienas Slot1: jungiklis, laikas, SOC, srovė |
| Iškrovimas | Vienas Slot1: jungiklis, laikas, SOC, srovė |

MPPT skenavimo valdikliai naujame profilyje nesukuriami. Likusių 2–6
slotų įjungimo bitai vis tiek skaitomi: prieš įjungiant paliktą slotą
ar valdant inverterio maitinimą, paslėpti aktyvūs slotai išjungiami ir
jų OFF patvirtinama. Kaukės rašomos tik turint visų 12 bitų skaitymą.

Baterijos SOC ir SOH telemetrija išlieka. Klaidingas įrenginio antraštės
baterijos indikatorius pašalintas: šiame profilyje nustatymams ir
telemetrijai nepriskiriama antraštę sukurianti `battery` device class.

## ON/OFF tyrimas

Rytinė 09:31:49 LT komanda per CID 5161 gavo API sėkmę, tačiau po 6 min.
registrai liko ON, AC galia ir eksportas tęsėsi. Taigi šio bandymo
negalima laikyti fiziniu išjungimu.

13:54 LT skaitymas parodė, kad CID 5162 grąžina būseną `190` ir Modbus
skaitymo komandą registrams 3006 / 43007. CID 5161 pakete negrąžinamas;
ankstesnis vieno CID skaitymas grąžino B0600. Hultenvp kodas turi abu
variantus, tačiau parenka juos pagal HMI versijos ribą. Naujas profilis
pirmenybę teikia realiai skaitomam CID 5162. Prieštaraujantys maitinimo
skaitymai stabdo įrašymą. Protokolo kvitas registruojamas be prisijungimo
duomenų.

**Fizinis ciklas patvirtintas 2026-09-12:** CID 5162 OFF išsiųstas
14:08:18 LT; HTTP baigėsi timeout 14:08:48. AC galia nukrito nuo 1203 W
iki 0 W 14:11:36, perskaityta OFF būsena gauta 14:14:51. ON bandymas
14:31:26–14:31:48 gavo protokolo kvitą registrui 43007 (`0xA7FF`, reikšmė
190), o ON skaitymas patvirtintas 14:37:55. Tai taip pat įrodo, kodėl
timeout negalima laikyti įrodymu, kad komanda nepasiekė inverterio.
AppDaemon Eimo `INVERTER_CONTROL_AVAILABLE` dabar `True`.

## Eksporto ribos mastelis

Patikrintas modelis: `3330`, `S6-EH3P10K02-NV-YD-L`. Šio modelio CID
499 / registras 43074 grąžina `10`, nors veikęs eksporto ribojimas yra
apie 1000 W. S6 Modbus įgyvendinimas šiam registrui taiko 100 W žingsnį.
Tik modeliui 3330 taikomas daugiklis 100 rodymui ir atvirkštinis
perskaičiavimas siunčiant. Kiti modeliai šios pataisos negauna.
Migracija fizinės eksporto ribos nekeitė.

## Patikra ir likusios ribos

43 automatiniai testai: laukimas ir naujas skaitymas, neaiškus įrašas,
plano atšaukimas bei pakeitimas, persikrovimas, bitų kaukės, slotų
stabdymo seka, laikrodžio eiga, klaidingi įvedimai, API klaidos,
transporto atšaukimas, bendras nepavykusių skaitymų limitas, modelio
3330 mastelis, ON/OFF varianto pasirinkimas, didėjanti pauzė, tikro
duomenų laiko šviežumas, laikrodžio šuolis ir sustojusio darbuotojo atkūrimas.
100 vienalaikių bandymų po klaidos teste išsiųsta tik viena HTTP užklausa,
99 bandymus sustabdė vietinis ribotuvas. Python kompiliacija ir
gyvos HA konfigūracijos patikra praėjo.

Po pirmo diegimo gyva patikra aptiko per dažną skaitymų kartojimą po
klaidos; tai pataisyta 4.1.1. 4.1.2 pridėtas CID 5162 aptikimas.
4.2.0 pridėtas nepriklausomas HTTP ribotuvas ir ryšio monitorius.
4.2.1 uždaryta istorinėje patikroje rasta perkrovimo išimtis; patvirtinimo
skaitymas tikrina ir monotoninį 360 s terminą, nepriklausomą nuo sieninio
laikrodžio korekcijos. [Duomenų kadrų ir užklausų laikų analizė](eimo_cloud_timing_2026-09-13.md).
SolisCloud `502`, `B0173`, DNS ir užklausų timeout dar pasitaiko. Vien HA
pakeitimų nepakanka pažadėti, kad debesijos sutrikimų nebebus.

## Monitoringas ir eksploatavimas

`sensor.solis_inverter_1033300254190112_cloud_api_health` rodo tikrų HTTP
užklausų, klaidų, vietoje atidėtų bandymų ir įrašų skaičių; pastarųjų
5 minučių ir valandos langus, kitą ryšio bandymą ir telemetrijos amžių.
`cloud_command_status` rodo aktyvią komandą, pageidaujamą reikšmę, tikrą
skaitymą ir ankstyviausią patvirtinimo laiką. Šie duomenys pridėti prie
Eimo valdymo skydelio. Monitoringo skaitikliai skaičiuojami nuo integracijos
paleidimo; HA istorija ir `custom_components.solis.cloud_diagnostics`
žurnalas leidžia palyginti skirtingus paleidimus. Ribos taikomos vienam
Solis API klientui; jos nekontroliuoja kitų telefonų ar atskirų programų.

Automatizacija `eimo_solis_cloud_monitor` sukuria HA pranešimą iš karto,
jei aptiktų daugiau kaip vieną įrašą per 5 min., arba po 15 min. trunkančios
stebimos ryšio / nepatvirtintos komandos būsenos. Pranešimas panaikinamas,
kai ryšys sveikas ir eilė laisva. Monitoringas pats inverterio neapklausia.

Neaiškaus įrašo tikslas automatiškai sutikrinamas grįžus ryšiui. Jeigu
inverteris nuolat grąžina kitą reikšmę, eilė lieka sustabdyta ir apie tai
praneša. Tai sąmoningas apsauginis stabdymas; nepalaikoma arba atmesta
komanda nėra kartojama be galo.

## Atsarginės kopijos ir atkūrimas

- Pradinė migracija: `/homeassistant/backups/eimo-unified-20260912T061101Z`.
- Prieš 4.2.0: `/homeassistant/backups/eimo-resilience-20260912T235740Z`,
  35 failai su SHA256 manifestu; atskirai ten perkeltas senas SCC katalogas.
- Prieš 4.2.1: `/homeassistant/backups/eimo-framing-20260913T063155Z`,
  penki tiksliai patikrinti integracijos failai ir SHA256 manifestas.
- Prieš atkuriant kodą išjungti Eimo plano vykdytoją. Atkurti kartu
  integracijos, paketo, skydelio ir atitinkamus AppDaemon failus, patikrinti
  HA konfigūraciją, tada vieną kartą perkrauti HA. Seną SCC grąžinti tik
  sąmoningai atkuriant ankstesnį dviejų integracijų variantą; jos įrašas
  pridedamas per HA nustatymus, neredaguojant `.storage` rankomis.
- AppDaemon šaltinių kontrolinis taškas saugomas atskiro repo šakoje
  [codex/eimo-unified-20260912](https://github.com/celadondeep/Solis/tree/codex/eimo-unified-20260912).
  Du migracijos pakeisti failai: `energy_system/profiles.py` ir
  `energy_system/supervisor.py`; kiti tos šakos failai yra ankstesnis gyvas kodas.

Individualūs pakeitimai saugomi šiame `ha-config` repo. Įprastas HACS
perdiegimas iš hultenvp gali juos perrašyti; būsimam atskiram fork perkelti
visą `custom_components/solis` katalogą, licenciją ir regresinius testus.

## Šaltiniai ir licencija

- [Hultenvp Solis Inverter](https://github.com/hultenvp/solis-sensor): pagrindas, telemetrija, ON/OFF variantai; Apache-2.0.
- [Solis Cloud Control](https://github.com/mkuthan/solis-cloud-control): kontrolinių funkcijų ir protokolo semantikos palyginimas.
- [Oficialus Solis Device Control API V2.0](https://oss.soliscloud.com/doc/SolisCloud%20Device%20Control%20API%20V2.0.pdf).
- [Oficialus komandų sąrašas](https://oss.soliscloud.com/doc/SolisCloud_control_api_command_list.xlsx).
- Vartotojo pateiktas `SolisCloud Platform API Document V2.0.3.pdf`: telemetrijos API.
- [Solis Modbus](https://github.com/Pho3niX90/solis_modbus): S6 registro 43074 mastelio palyginimas.

Nauja komandų eilė ir HA adapteriai parašyti šiam profiliui; antros
integracijos paketas neįtraukiamas kaip priklausomybė. Išsaugota bazės
Apache-2.0 licencija. Tai individualus profilis, o ne universaliai su
visais Solis modeliais patvirtintas leidimas.
