# trades-skills

Claude skills for the trades: code-cited calculations and paperwork for electricians, plumbers, HVAC techs and homeowners.

> **Calculation aids, not professional advice.** Nothing in this repository is engineering, legal, safety or code-compliance advice, and nothing here replaces the adopted code book, a licensed tradesperson or the permit process. The rules and tables were entered from public sources and have not been verified against the code book. Electrical work can cause fire, injury and death. Provided as is, without warranty. See each plugin's `DISCLAIMER.md`.

## residential-load-calc

Tell Claude what is in the house and what is being added. It answers "can this service take it?" with a worksheet an inspector can follow.

- **Three methods:** the NEC optional method (220.82), the existing-dwelling method (220.83) and recorded demand (220.87), for one dwelling unit.
- **Edition aware:** 2017, 2020, 2023 and 2026. The 2026 NEC moves these rules to Article 120 and changes the factors; 2026 support is provisional and flagged on every run.
- **Shows the disagreements:** editions before 2026 do not say how an EV charger enters these calculations. The worksheet shows the result under every reading an inspector may require, so you know what to ask before buying anything.
- **When it does not fit:** the largest load-managed charger setting that fits, and the smallest standard service size that works.
- **Cites, does not copy:** section numbers on every line, no code text.

It ships a standard-library Python script. It reads one job file, prints a worksheet, makes no network requests and writes no files:

```bash
python scripts/load_calc.py job.json
```

Out of scope: multifamily, commercial, 3-phase, the standard method, conductor sizing and voltage drop.

## circuit-sizing

Ask what a circuit needs and get the steps, not just the answer.

- **Wire and breaker:** smallest conductor and overcurrent device for a load, with the continuous-load rule, termination temperature, ambient and bundling corrections, and the equipment ground.
- **Voltage drop:** volts and percent for a run, the longest run within the target, and the conductor that fixes it.
- **Conduit fill:** smallest EMT, IMC, RMC or PVC conduit for a mix of conductors, or the most that fit in the one you have.
- **Box fill:** required volume from conductors, clamps, devices and grounds, and the smallest standard boxes that hold it.
- **Air conditioners and heat pumps:** wire and breaker from the unit's nameplate.

```bash
python scripts/circuit_calc.py job.json
```

Out of scope: motors sized from horsepower, welders, parallel conductors, anything over 600 A.

## Install

In Claude Code:

```
/plugin marketplace add chrisamz/trades-skills
/plugin install residential-load-calc@trades-skills
/plugin install circuit-sizing@trades-skills
```

## Tests

Each plugin with a script has regression checks whose expected values were worked by hand:

```bash
python plugins/residential-load-calc/tests/test_load_calc.py
python plugins/circuit-sizing/tests/test_circuit_calc.py
```

## Trademarks

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association. This project is not affiliated with or endorsed by NFPA.

## License

MIT. See `LICENSE`.
