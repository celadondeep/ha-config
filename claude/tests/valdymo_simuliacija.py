#!/usr/bin/env python3
"""
Valdymo logikos simuliacija ir testai — Namai SE + Eimo SE.

Paleidžia pagrindinius sprendimų taškus per įvairias situacijas ir tikrina:
  1) ar sprendimai atitinka lauktus (režimas, langai, apsaugos);
  2) ar nėra loginių KONFLIKTŲ (dvi automatikos vienu metu daro priešingus dalykus).

Formulės atkartotos iš:
  - automations.yaml: solis_morning_mode, solis_daytime_feedin_tou,
    solis_low_soc_night_shutdown, solis_morning_inverter_power_on
  - packages/eimo.yaml: solis_daytime_discharge_eimo
  - energy_manager*.py: HEALTH_SOC_MIN, BIG_DAY_KWH

Paleisti:  python3 /config/claude/tests/valdymo_simuliacija.py
(Grynai loginis — HA nereikia. Keitus YAML logiką, atnaujink ir čia.)
"""

# ── Parametrai (turi sutapti su gyva konfigūracija) ───────────────────────
NAMAI = dict(floor=12, big_day=28, health_min=20, kwh_per_soc=0.16,
             export_kw=1.0, min_soc=10)
EIMO  = dict(floor=6,  big_day=28, health_min=20, kwh_per_soc=0.1434,
             export_kw=1.0, min_soc=5)

# ── Sprendimų formulės ────────────────────────────────────────────────────
def morning_mode(fc, soc, cons):
    """solis_morning_mode: aukšta diena → Feed-in, kitaip Self-Use."""
    thr = (100 - soc) * 0.16 + cons * 0.5
    return "Feed-in Priority" if fc > thr else "Self-Use", round(thr, 1)

def shave_cutoff(fc, p):
    return 90 if fc > p["big_day"] else 80

def feedin_tou_branch(surplus, soc, pv, load, slot_on, slot_cutoff, fc, grid_imp, p,
                      storm=False, hh=12, power_on=True):
    """Kuri solis_daytime_feedin_tou / daytime_discharge_eimo šaka suveiktų.
    Įskaito automatikos apsaugines SĄLYGAS (langas 07:00–19:30, audra off,
    inverteris on) — už jų ribų automatika nesuveikia visai."""
    if storm:
        return "nieko (audra)"
    if not power_on:
        return "nieko (inverteris off)"
    if not (7 <= hh < 19.5):
        return "nieko (ne dienos langas)"
    slot_active = slot_on
    shave = shave_cutoff(fc, p)
    if surplus > 1 and soc >= p["floor"] + 5 and (not slot_active or slot_cutoff >= 80):
        return "1_floor_eksportas"
    if slot_active and slot_cutoff >= 80 and grid_imp:
        return "1b_skutimo_atleidimas"
    if soc >= shave + 1 and not slot_active:
        return "2_virsunes_skutimas"
    if slot_active and slot_cutoff < 80 and soc <= p["floor"]:
        return "3_dugno_atsistatymas"
    if surplus < 0.2 and slot_active and slot_cutoff < 80:
        return "4_perteklius_dingo"
    return "nieko"

def dugno_rest(soc, pv, load, night, hh):
    """solis_low_soc_night_shutdown: ar inverteris pailsi (TIK naktis;
    dieninė pv<load šaka pašalinta 2026-07-24 — apsaugo overdischarge=11)."""
    night_band = soc <= 6 or (soc <= 16 and (hh >= 20.5 or hh < 10))
    return night and night_band

def morning_on_blocked(soc, eimo_pv, storm):
    """solis_morning_inverter_power_on: blokavimo nebėra (2026-07-26 pašalinta
    07-22 sąlyga soc<=12 ir eimo<1200 — ji atidėdavo įjungimą debesuotą rytą;
    dugną saugo overdischarge, ne inverterio laikymas išjungto)."""
    return False

def health_target(base_target, fc, soc, p):
    """energy_manager: nuosaikią dieną target ne žemiau health_min."""
    if fc <= p["big_day"]:
        return max(base_target, p["health_min"])
    return base_target

def dynamic_night_stage(soc, target, hh, p, sleep_enabled=True,
                        morning_h=6.0, exec_start_h=19.5):
    """Supaprastintas energy_manager night_plan_cycle modelis."""
    target = max(target, p["floor"])
    if soc <= target + 1:
        return "DONE"

    # Linijinė nakties laiko ašis: 20:00=20, 05:00=29.
    now_h = hh + (24 if hh < 12 else 0)
    morning = morning_h + 24
    exec_start = exec_start_h

    if hh >= 18 and now_h < exec_start:
        return "WAIT_EVENING"

    if not sleep_enabled:
        return "EVENING_BOOST" if hh >= 18 else "DAWN_FINISH"

    sleep_soc = max(target, p["health_min"])
    if soc > sleep_soc + 1:
        return "EVENING_BOOST"

    if target < sleep_soc:
        dawn_kw = p["export_kw"] + 0.30 + 0.14
        energy = max(0.0, (soc - target) * p["kwh_per_soc"])
        dawn_hours = energy / dawn_kw + 0.20
        dawn_start = morning - dawn_hours
        return "SLEEP" if now_h < dawn_start else "DAWN_FINISH"

    return "DONE"

def run_night_plan_tests():
    cases = [
        ("vakaro boost 70→20", NAMAI, 70, 20, 20.0, True, "EVENING_BOOST"),
        ("žemas target: miego langas", NAMAI, 20, 12, 23.0, True, "SLEEP"),
        ("žemas target: dawn finish", NAMAI, 20, 12, 5.0, True, "DAWN_FINISH"),
        ("target pasiektas", NAMAI, 12, 12, 5.5, True, "DONE"),
        ("Eimo be power-cycle naktį aktyvus", EIMO, 60, 30, 23.0, False, "EVENING_BOOST"),
        ("Eimo po vidurnakčio aktyvus", EIMO, 40, 20, 3.0, False, "DAWN_FINISH"),
    ]
    errors = 0
    print(f"\n{'='*70}\n  DINAMINIS NAKTIES PLANAS\n{'='*70}")
    for name, p, soc, target, hh, sleep_enabled, expected in cases:
        got = dynamic_night_stage(soc, target, hh, p, sleep_enabled=sleep_enabled)
        ok = got == expected
        print(f"  {'✓' if ok else '❌'} {name}: {got} (tikėtasi {expected})")
        if not ok:
            errors += 1
    return errors

# ── Scenarijai ────────────────────────────────────────────────────────────
# hh — vietos valanda (float). pv/load — W. fc — koreguota dienos prognozė kWh.
SCENARIJAI = [
    dict(v="Saulėta didelė diena, vidudienis, pusiau pilna",
         fc=32, soc=50, cons=10, pv=5500, load=300, hh=13, eimo_pv=4500,
         surplus=8, slot_on=False, slot_cutoff=12, grid_imp=False, storm=False,
         laukiam_rezimas="Feed-in Priority"),
    dict(v="Saulėta didelė diena, baterija pilna (skutimas)",
         fc=32, soc=85, cons=10, pv=5000, load=300, hh=14, eimo_pv=5000,
         surplus=3, slot_on=False, slot_cutoff=90, grid_imp=False, storm=False,
         laukiam_rezimas="Feed-in Priority"),
    dict(v="Nuosaiki diena, viskas tilps",
         fc=14, soc=30, cons=12, pv=2000, load=400, hh=11, eimo_pv=1800,
         surplus=-3, slot_on=False, slot_cutoff=12, grid_imp=False, storm=False,
         laukiam_rezimas="Self-Use"),
    dict(v="Debesuotas rytas, baterija tuščia (dugno rest)",
         fc=10, soc=11, cons=12, pv=300, load=600, hh=9, eimo_pv=500,
         surplus=-2, slot_on=False, slot_cutoff=12, grid_imp=False, storm=False,
         laukiam_rezimas="Self-Use"),
    dict(v="Naktis, baterija vidutinė (naktinė iškrova galima)",
         fc=0, soc=50, cons=0, pv=0, load=2000, hh=23, eimo_pv=0,
         surplus=-5, slot_on=True, slot_cutoff=20, grid_imp=False, storm=False,
         laukiam_rezimas=None),
    dict(v="Naktis, baterija ties dugnu (churn apsauga)",
         fc=0, soc=12, cons=0, pv=0, load=400, hh=2, eimo_pv=0,
         surplus=-5, slot_on=False, slot_cutoff=20, grid_imp=False, storm=False,
         laukiam_rezimas=None),
    dict(v="Vakaras, skutimo langas užšaldė (importuoja)",
         fc=20, soc=80, cons=8, pv=120, load=900, hh=18.5, eimo_pv=200,
         surplus=-1, slot_on=True, slot_cutoff=80, grid_imp=True, storm=False,
         laukiam_rezimas=None),
    dict(v="Audros režimas dieną",
         fc=30, soc=40, cons=10, pv=5000, load=300, hh=12, eimo_pv=4000,
         surplus=5, slot_on=False, slot_cutoff=12, grid_imp=False, storm=True,
         laukiam_rezimas=None),
]

def run(p, name):
    print(f"\n{'='*70}\n  {name}\n{'='*70}")
    klaidos = 0
    for s in SCENARIJAI:
        rez, thr = morning_mode(s["fc"], s["soc"], s["cons"])
        rest = dugno_rest(s["soc"], s["pv"], s["load"], s["pv"] == 0, s["hh"])
        br = feedin_tou_branch(s["surplus"], s["soc"], s["pv"], s["load"],
                               s["slot_on"], s["slot_cutoff"], s["fc"],
                               s["grid_imp"], p, storm=s["storm"], hh=s["hh"],
                               power_on=not rest)
        blocked = morning_on_blocked(s["soc"], s["eimo_pv"], s["storm"])
        ht = health_target(15, s["fc"], s["soc"], p)

        # ── KONFLIKTŲ patikros ──
        konfliktai = []
        # (a) dugno-rest išjungia inverterį, o feedin_tou tuo pat metu bando eksportuoti
        if rest and br.startswith(("1_", "2_")):
            konfliktai.append("dugno-rest IŠJUNGIA, o feedin_tou EKSPORTUOJA (konfliktas)")
        # (b) [pašalinta 2026-07-26] ryto įjungimo blokavimo nebėra — dieną
        #     inverteris visada įjungtas, dugną saugo overdischarge=11 %.
        # (c) audra, bet siūloma eksportuoti
        if s["storm"] and br.startswith(("1_", "2_")):
            konfliktai.append("audros režimas, bet feedin_tou eksportuoja")
        # (d) lauktas režimas
        if s["laukiam_rezimas"] and rez != s["laukiam_rezimas"]:
            konfliktai.append(f"režimas {rez}, tikėtasi {s['laukiam_rezimas']}")

        status = "❌" if konfliktai else "✓"
        print(f"  {status} {s['v']}")
        print(f"      režimas={rez} (thr={thr}) | feedin_tou={br} | "
              f"dugno_rest={rest} | įjung.blokuotas={blocked} | health_target≥{ht}")
        for k in konfliktai:
            print(f"      ⚠️  {k}")
            klaidos += 1
    return klaidos

if __name__ == "__main__":
    total = run(NAMAI, "NAMAI SE") + run(EIMO, "EIMO SE") + run_night_plan_tests()
    print(f"\n{'='*70}")
    print(f"  REZULTATAS: {'VISKAS ŠVARU ✓' if total == 0 else f'{total} KONFLIKTŲ ❌'}")
    print(f"{'='*70}")
    exit(1 if total else 0)
