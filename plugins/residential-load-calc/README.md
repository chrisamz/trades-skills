# residential-load-calc

Answers "can this house service take the added load?" with a worksheet an inspector can follow. Built for electricians pricing EV charger, heat pump and electrification jobs, and for homeowners who want to know what to expect before calling one.

> **Calculation aid, not professional advice.** This plugin does not replace the adopted code book, a licensed electrician or the permit process. Its rules were implemented from public summaries and were not verified against code text. Electrical work can cause fire, injury and death. Provided as is, without warranty. Read `DISCLAIMER.md` before relying on it.

## What it does

- Runs the NEC optional method (220.82), the existing-dwelling method (220.83) and the recorded-demand method (220.87) for one dwelling unit.
- Knows the 2017, 2020, 2023 and 2026 editions. The 2026 NEC moves these rules to Article 120 and changes the factors; 2026 support is provisional and flagged as such on every run.
- Cites the code section for every line without reproducing code text.
- Shows how the answer changes under other readings an inspector may require, such as an EV charger taken at 100% or 125% instead of inside the demand tiers.
- Gives no "fits" verdict when the method is not permitted for the job as entered (the optional method on a service under 100 A, or a 30-day recording on a service with solar); the worksheet says so in place of the verdict and gives the reason.
- When the load does not fit, lists the options: load management, recorded demand, or the smallest standard service size that works.

## What it runs

One Python script, `skills/residential-load-calc/scripts/load_calc.py`, standard library only. It reads one JSON job file and prints a worksheet. It makes no network requests and writes no files.

## Example prompts

1. "200 amp service, 2,400 sq ft house, electric range, dryer, water heater and a 3.5 ton AC with a 10 kW furnace. Customer wants a 48 amp EV charger. We are on the 2023 code. Does it fit?"
2. "I have a 100 amp panel and want to replace my gas furnace with a heat pump. My utility says my peak demand last year was 7.9 kW. Do I need a service upgrade?"
3. "Size the service for a new 2,400 sq ft all-electric house under the 2026 NEC with a 48 amp charger."

Sample job files for each are in `examples/`.

## Limits

One dwelling unit, single-phase 3-wire, 100 A or larger for the optional method. No multifamily, commercial or 3-phase. Service capacity and the minimum circuit rating for a new EV charger only: conductor sizing and voltage drop are separate checks.

## Disclaimer

The adopted code edition, local amendments and the authority having jurisdiction govern. A worksheet that says "fits" is not a permit and does not authorize any installation. Installation work requires a permit and, in most places, a licensed electrician. Every worksheet ends with a notice saying so. Full terms are in `DISCLAIMER.md`.

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association. This project is not affiliated with or endorsed by NFPA.

## Tests

```
python tests/test_load_calc.py
```

## Install

```
/plugin marketplace add chrisamz/trades-skills
/plugin install residential-load-calc@trades-skills
```
