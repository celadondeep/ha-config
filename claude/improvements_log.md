# Energijos valdymo tobulinimo žurnalas

Viena eilutė per dieną: data | išvada | siūlymas.

2026-06-12 | PV prognozė 96 % tiksli, bet korekcijos ir suvartojimo modelio failai neišsisaugo (kelio defektas AppDaemon konteineryje), naktį 6 force-charge ciklai ties 10 % SOC, po HA restarto 22:39 target_soc užstrigo ties 100 % | Pataisyti CORRECTION_FILE/MODEL_FILE kelius į os.path.dirname(__file__); po restarto 18:00–06:00 perskaičiuoti target; patikslinti kainų input'us (buy=0.0/sell=0.25 atrodo sukeisti)

