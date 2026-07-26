# Energijos valdymo sistemos dokumentacija

Gyvi dokumentai apie sistemos veikimą, logikas ir taisykles. Prižiūri
Claude (kasdienis auditas + sesijos): **kiekvienas logikos pakeitimas privalo
atsispindėti čia** — atnaujinamas atitinkamas skyrius ir įrašas žurnale.

| Failas | Kas viduje |
|---|---|
| [⭐ vizija.md](vizija.md) | **TAVO** dokumentas — kaip nori, kad sistema veiktų. Claude/auditas jo neperrašo, tik skaito |
| [architektura.md](architektura.md) | Dvi elektrinės, komponentai, kas ką valdo, sensorių nuosavybė |
| [taisykles.md](taisykles.md) | Saugos ribos ir vartotojo taisyklės — NIEKADA nelaužomos |
| [valdymo_logika.md](valdymo_logika.md) | Paros ciklas: režimai, slotai, taikiniai, slenksčiai (abi elektrinės) |
| [eso.md](eso.md) | ESO integracija: importas, pasaugojimo bankas, atjungimai, 2FA |
| [prognozes.md](prognozes.md) | Solcast korekcijos, vartojimo modelis, orai |
| [zurnalas.md](zurnalas.md) | Sprendimų žurnalas — kas, kada ir kodėl pakeista |

Susiję ne šiame kataloge:
- `claude/daily_energy_review.md` — kasdienio audito procedūra (07:10)
- `packages/*.yaml`, `automations.yaml` — vykdomoji konfigūracija (komentarai
  failuose — pirminis tiesos šaltinis smulkmenoms)
- AppDaemon logika — atskiras git repo (`celadondeep/Solis`),
  `/config/appdaemon/apps/`
