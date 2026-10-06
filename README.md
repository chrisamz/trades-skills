# trades-skills

Claude skills for the trades: code-cited calculations and paperwork for electricians, plumbers, HVAC techs and homeowners.

> **Calculation aids, not professional advice.** Nothing in this repository is engineering, legal, safety or code-compliance advice, and nothing here replaces the adopted code book, a licensed tradesperson or the permit process. The rules were implemented from public summaries and have not been verified against code text. Electrical work can cause fire, injury and death. Provided as is, without warranty. See each plugin's `DISCLAIMER.md`.

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

## Install

In Claude Code:

```
/plugin marketplace add chrisamz/trades-skills
/plugin install residential-load-calc@trades-skills
```

## Tests

Each plugin with a script has regression checks whose expected values were worked by hand:

```bash
python plugins/residential-load-calc/tests/test_load_calc.py
```

## Trademarks

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association. This project is not affiliated with or endorsed by NFPA.

## License

MIT. See `LICENSE`.
