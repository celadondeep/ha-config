# Vartojimo modelio V4 diegimo patvirtinimas

Patikrinta 2026-09-18T07:28:42.152374+03:00 (Lietuvos laiku).

- Abiejų elektrinių modelio versija 4; 30 parų langas išlaikytas.
- Namai: `rolling_mean`; Eimo: `rolling_mean_weekday_shrinkage`. Tas pats bendras kodas, atskiros istorijos ir profilių parinktys.
- Patikrinti visi 13 pakeistų gyvų failų SHA-256; neatitikimų nėra.
- Abu planuotojai ir vykdytojai `ok`, abu branduoliai `normal`.
- Eimo Cloud `healthy`, komandos `idle`; patikros metu 2 API užklausos ir 0 įrašymų per paskutines 5 minutes.
- HA konfigūracija validi. Po paleidimo patikrintame AppDaemon žurnalo lange ERROR įrašų nerasta.
- 76 vietiniai AppDaemon testai sėkmingi, taip pat JS vartojimo kortelės atvaizdavimas su 0, 1 ir 14 patikrintų prognozių. Patikrintos abi gyvos `vartojimas` peržiūrų konfigūracijos; autentifikuota naršyklės ekrano patikra neatlikta.
- Prognozių žurnalas patikrintas failuose po pakartotinio AppDaemon paleidimo. Rugsėjo 19 d. iš anksto išsaugota Namų prognozė 17,17 kWh, Eimo 10,18 kWh; abu mokyti tik iki rugsėjo 17 d. Žurnalo prognozės nesikeitė po perkrovimo.
- Gyvas tikslumas dabar `collecting` ir 0 patikrintų parų. Pirmas rezultatas galimas rugsėjo 20 d. po vietinės istorijos atnaujinimo, jei rugsėjo 19 d. matavimai bus pakankamai pilni. Istorinio palyginimo rezultatai neperkelti į gyvo tikslumo skaitiklį.

Kodo commitai: [Solis e55964f](https://github.com/celadondeep/Solis/commit/e55964faf9df69e49120c419e63ec435f56ed947), [HA konfigūracija cc3e765](https://github.com/celadondeep/ha-config/commit/cc3e76530ef2e48c13007d18f7615d3f75dbee10).

CI: [bendri modelio ir planuotojo testai — success](https://github.com/celadondeep/Solis/actions/runs/35307050104), [HA konfigūracijos patikra — success](https://github.com/celadondeep/ha-config/actions/runs/35307052252).

[Analizė, matavimo ribos ir atkūrimo instrukcija](consumption_model_v4.md). [Visų kandidatų skaitiniai palyginimai](consumption_model_v4_metrics.json).
