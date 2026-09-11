# Eimo SolisCloud dienos stabilumo analizė — 2026-09-11

## Simptomas

Eimo SE SolisCloud ryšys daugiausia prastėja dieną; vakare ir naktį ryšys
pastebimai stabilesnis.

## Istoriniai įrodymai

2026-07-18 apie 15:00 SolisCloud grąžino `B0072` (`The device is offline`) ir
senas retry mechanizmas kartojo užklausas 1/2/4/8 s intervalais. Maždaug 15:56
tas pats inverteris vėl sėkmingai atsakė į pilną `atReadBatch` per ~1.2 s.
Tai labiau atitinka laikiną device-control kanalo/cooldown būseną nei pastovų
interneto ar autentifikacijos gedimą.

## Rastas mūsų apkrovos modelis

Dienos automatika `solis_daytime_discharge_eimo` tikrinama kas 15 min ir
perėjimo metu gali paprašyti kelių atskirų cloud parametrų:

- slot1 discharge switch — CID 5922
- slot1 discharge time — CID 5964
- slot1 discharge current — CID 5967
- slot1 discharge SOC — CID 5965
- storage mode — CID 636

Ankstesnis API klientas turėjo `Semaphore(1)`, bet neturėjo minimalaus intervalo
tarp užklausų. Be to, kiekvienas control sukeldavo papildomą coordinator refresh.
Eimo periodinis `atReadBatch` buvo paleistas kas 1 min, nors SolisCloud įrenginio
duomenų upload dažnis yra apie 5 min.

## Įgyvendintas stabilumo sluoksnis

### 1. Polling 1 min -> 5 min

Eimo periodinis `atReadBatch` suderintas su SolisCloud telemetrijos 5 min
atnaujinimu. Control komandos dėl to nevėluoja — jos siunčiamos iškart.

### 2. Request pacing

API kliente:

- visos device-control užklausos serializuotos kaip anksčiau;
- minimalus tarpas po read: 0.75 s;
- po `/v2/api/control`: 2.5 s settle langas;
- timeout skaičiuojamas tik tada, kai requestas jau pasiekė lokalaus queue galvą.

### 3. Post-write refresh coalescing

Eimo confirmation refresh cooldown pakeistas iš 10 s į 30 s. Keli susiję slot
write'ai turi baigtis vienu patvirtinimo skaitymu, o ne read-after-every-write.

### 4. Redundant write suppression

Jei paskutinė patvirtinta Eimo CID reikšmė jau lygi pageidaujamai reikšmei,
`/control` išvis nesiunčiamas. Tai automatiškai sumažina 4–5 komandų YAML
konfigūravimo sekas iki tik tų CID, kurie realiai pasikeitė.

### 5. B0072 nėra greitai retry'inamas

`B0072 Device is offline` nebėra kartojamas 1/2/4/8 s seka. Ši būsena paliekama
kitam suplanuotam/confirmation ciklui. Timeout ir transporto klaidos išlaiko
normalų exponential backoff.

### 6. Tik patvirtinta būsena rodoma HA

Anksčiau coordinatorius pageidaujamą CID reikšmę įrašydavo lokaliai PRIEŠ
SolisCloud patvirtinimą. Jei write baigdavosi B0072/timeout, HA galėjo rodyti
komandą kaip įvykdytą. Dabar coordinator data keičiama tik po sėkmingo
`/control` atsakymo.

## Forensinė diagnostika

`scripts/analyze_eimo_cloud_log.py` grupuoja logus valandomis ir prie kiekvieno
B0072/timeout parodo control komandas per ankstesnes 5/15/30 min bei jų CID.

Paleidimas:

```bash
ha core logs | python3 /config/scripts/analyze_eimo_cloud_log.py
```

arba iš išsaugoto log failo:

```bash
python3 /config/scripts/analyze_eimo_cloud_log.py /config/home-assistant.log
```

## Gyvas diegimas

Atnaujintas `scripts/deploy_eimo_solis_stage1.sh` dabar diegia 6 failus:

- `__init__.py`
- `api/solis_api.py`
- `coordinator.py`
- `entity.py`
- `inverters/inverter_factory.py`
- `utils/retry_policy.py`

Jis daro backup, `py_compile`, išvalo `__pycache__` ir restartuoja HA Core.
Rollback naudoja tą patį 6 failų rinkinį.

Backup Git branch prieš stabilumo pakeitimus:
`backup/eimo-cloud-stability-20260911`.

## Ką stebėti po live deploy

Svarbiausias testas — dienos laikotarpis 07:00–19:30:

1. `atReadBatch` turi būti maždaug 5 min ritmu, ne kas minutę.
2. Loguose turi atsirasti `control skipped (already confirmed)` — tai gerai.
3. Realių `/control` CID komandų skaičius turi smarkiai sumažėti.
4. Jei B0072 lieka, forensinis analizatorius parodys, ar jis seka po konkretaus
   CID (5922/5964/5967/5965/636), po bendro komandų skaičiaus, ar atsiranda ir
   visiškai be control komandų.
5. Jei B0072 kartojasi be jokių preceding control komandų, problema labiau
   tikėtina SolisCloud/logger/device ryšio pusėje, ne mūsų valdymo burste.

## Galimas Stage-2 metodas

Jei sumažinus write/read apkrovą B0072 lieka, verta atskirti telemetry nuo
control kanalo:

- telemetry: SolisCloud Data Access 5 min arba Real-time Data Forwarding;
- control: tik reti device-control/strategy write'ai;
- trečiųjų šalių OAuth integracijai Solis rekomenduoja `strategySetting` kaip
  pirmą pasirinkimą, `control` — kaip papildomą metodą.

Migracija į OAuth/strategy API nedaroma aklai — jai reikia atskiro Solis
OAuth/third-party onboarding ir atitinkamų credentials.
