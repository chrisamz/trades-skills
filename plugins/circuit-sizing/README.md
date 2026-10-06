# circuit-sizing

Answers the sizing questions that come up on almost every circuit, with a worksheet that shows each step and the code section behind it. Built for electricians and apprentices who want a second check, and for homeowners who want to understand what a job needs before calling one.

> **Calculation aid, not professional advice.** This plugin does not replace the adopted code book, a licensed electrician or the permit process. Its tables and rules were entered from public sources and cross-checked against independent published copies, not against the code book itself. An undersized wire or an overfilled box is a fire risk. Provided as is, without warranty. Read `DISCLAIMER.md` before relying on it.

## What it does

- **Wire and breaker:** smallest conductor and the overcurrent device for a load, with the 125% continuous-load rule, termination temperature, ambient correction, bundling adjustment, small-conductor limits and the equipment ground. Reports what changes if the terminals are 60 C.
- **Air conditioners and heat pumps:** wire and breaker from the unit's nameplate (minimum circuit ampacity and maximum overcurrent device), which follow different rules from general loads.
- **Voltage drop:** drop in volts and percent for a run, the longest run that stays within the target, and the conductor that fixes it. In a wire calculation it upsizes for you and resizes the ground to match.
- **Conduit fill:** smallest EMT, IMC, RMC or PVC conduit for a mix of conductors, or a check of the conduit you have, and the most same-size conductors that fit.
- **Box fill:** required volume from conductors, clamps, devices and grounds, with the rule for grounds that applies to your code edition, and the smallest standard boxes that hold it.

Every worksheet cites section and table numbers without reproducing code text, and ends with a notice.

## What it runs

One Python script, `skills/circuit-sizing/scripts/circuit_calc.py`, standard library only. It reads one JSON job file and prints a worksheet. It makes no network requests and writes no files.

## Example prompts

1. "What wire and breaker do I need for a 48 amp EV charger, 50 foot run in EMT?"
2. "I'm running a 20 amp circuit 150 feet to a shed in 12-2 Romex. Is voltage drop a problem?"
3. "How many 12 gauge THHN can I pull in 3/4 EMT, and what size box do I need for two 12-2 cables and a receptacle?"

Sample job files are in `examples/`.

## Limits

Up to 600 A, copper and aluminum, 14 AWG to 600 kcmil, one conductor per phase. General loads, plus air-conditioning and heat-pump equipment from its nameplate. Motors sized from horsepower, welders and parallel conductors are out of scope. Voltage drop assumes a power factor of 0.85 or better for large conductors. The 2026 code edition was reviewed only through published summaries; the core tables are reported unchanged and its additions are not implemented.

## How the tables were checked

The ampacity, temperature-correction, impedance and conduit tables were compared with independent published copies; the regression tests reproduce more than 150 published conductor counts across five raceway types. What was and was not checked is listed in `skills/circuit-sizing/references/method-notes.md`.

## Disclaimer

The adopted code edition, local amendments and the authority having jurisdiction govern. A worksheet is not a permit and does not authorize any installation. New circuits require a permit in most places, and work inside a panel is a job for a licensed electrician. Full terms are in `DISCLAIMER.md`.

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association. This project is not affiliated with or endorsed by NFPA.

## Tests

```
python tests/test_circuit_calc.py
```

## Install

```
/plugin marketplace add chrisamz/trades-skills
/plugin install circuit-sizing@trades-skills
```
