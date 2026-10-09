# Method notes

What `load_calc.py` implements, why, and where inspectors disagree. Section numbers are for the 2017-2023 NEC; in the 2026 NEC, Article 220 became Article 120 (220.82 is 120.82, and so on).

## Contents

1. Edition differences
2. 220.82 optional method
3. 220.83 existing dwelling
4. 220.87 recorded demand
5. EV chargers: the three readings
6. Load management
7. Confidence in each rule

## 1. Edition differences

| | 2017 / 2020 | 2023 | 2026 (provisional) |
|---|---|---|---|
| Article | 220 | 220 | 120 |
| General lighting | 3 VA per sq ft | 3 VA per sq ft | 2 VA per sq ft |
| Optional method first tier at 100% | 10 kVA | 10 kVA | 8 kVA |
| Remainder | 40% | 40% | 40% |
| EVSE load value | nameplate | larger of nameplate or 7,200 VA (220.57) | nameplate; 7,200 VA if unknown (120.57) |
| EVSE in optional method | not addressed, see section 5 | not addressed, see section 5 | 100%, outside the tiers (120.82(D)) |
| Existing dwelling, added load | 8 kVA / 40%, with new HVAC at 100% | same | existing 8 kVA / 40%; new EVSE 80%, new central resistance heat 80%, other new loads 50% |
| 125% for continuous loads inside the load calc | debated | debated | not required (120.5(E)) |

States adopt editions years apart and amend them. Always confirm the adopted edition and local amendments.

## 2. 220.82 optional method

Applies to one dwelling unit served by a single 120/240 V or 208Y/120 V 3-wire service or feeder of 100 A or more. If the rating entered is under 100 A the script still shows the arithmetic, but prints "NOT A VALID RESULT" in place of a fits verdict (`fits` is null and `not_permitted` carries the reason in the JSON output).

General loads are summed, then the first tier is taken at 100% and the rest at 40%:

- floor area times the lighting unit load
- 1,500 VA per small-appliance circuit and per laundry circuit
- nameplate of every appliance fastened in place or on its own circuit: range, ovens, cooktop, dryer, water heater, dishwasher, disposal, microwave, well pump, hot tub and so on
- nameplate of permanently connected motors not already counted

Heating and cooling is the single largest of these, added after the tiers:

1. air conditioning at 100%
2. heat pump at 100% (no supplemental heat)
3. heat pump at 100% plus supplemental heat at 65%; if the compressor is locked out while the strips run, the compressor is left out
4. electric space heat, fewer than four separately controlled units, at 65%
5. electric space heat, four or more separately controlled units, at 40%
6. thermal storage or other heating expected to run continuously at full load, at 100%

Use nameplate VA (volts times amps), not cooling tonnage or BTU. For a condenser, use minimum circuit ampacity only if rated-load amps are unavailable; it overstates the load slightly.

## 3. 220.83 existing dwelling

Used to check whether an existing service can take added load.

**2017-2023.** Two cases:

- (A) No heating or cooling equipment is being added: all loads, existing and new, go in one pool; first 8 kVA at 100%, remainder at 40%.
- (B) Heating or cooling equipment is being added: heating and cooling come out of the pool and are taken at 100% (the larger of the two, since they don't run together, 220.60); everything else is pooled at 8 kVA / 40%. Space heat with four or more separately controlled units stays in the pool.

The script picks (B) when any HVAC entry is marked new.

Disputed point: under (A), does existing heating and cooling go in the pool? The list of loads does not name it separately, and the common reading treats it as fixed equipment in the pool (`hvac_83a: tiered`, the default). Some inspectors want it at 100% (`hvac_83a: full`). The worksheet shows both.

**2026.** One table. Existing loads are pooled at 8 kVA / 40%. Each new load is added at its own factor: EVSE 80%, central electric resistance heat 80%, anything else 50%. Whether heating or cooling is being added no longer changes the method. The script treats a new heat pump or air conditioner as "other new load" at 50%; that classification is the least certain part of the 2026 implementation.

## 4. 220.87 recorded demand

Existing load is the recorded maximum demand times 125%. New load is added on top. The sum must not exceed the service or feeder rating.

Data that qualifies:

- maximum demand for a one-year period, usually utility interval data; or
- by exception, a continuous recording of at least 30 days of 15-minute average demand on the highest loaded phase, taken while the home is occupied, and adjusted to include the larger of heating or cooling and other seasonal loads. The exception is not available where the service has solar, wind or peak shaving. A job entered that way gets "NOT A VALID RESULT" in place of a fits verdict, the same as an optional-method run under 100 A; the script never reports that a load fits under a method the job does not qualify for.

Practical traps:

- Monthly kWh is not demand. The input must be a peak kW or amps value.
- Hourly smart-meter data understates the 15-minute peak. Many jurisdictions accept it anyway, some require a margin; ask.
- With solar, the utility meter sees net import. The house peak can be larger than the meter shows.
- If the peak is given in kW, the script takes kW as kVA unless a power factor is supplied.
- The 2026 edition reportedly allows removed loads to be subtracted. Single source; the script applies it only for 2026 and flags it.

## 5. EV chargers: the three readings

Before 2026 the optional and existing-dwelling methods do not say where an EV charger goes. Three readings are in use, and the difference is often the whole answer on a 100 A or 125 A service:

| Reading | `evse_treatment` | What it does |
|---|---|---|
| Appliance on its own circuit | `general` | In the pool, so most of it lands in the 40% tier. Default for 2017-2023. |
| Full load | `full` | 100% of the load value, added after the tiers. What the 2026 code requires for 120.82. |
| Continuous load | `continuous_125` | 125%, added after the tiers. The most conservative; some AHJs require it. |

For 220.87 the choice is between `full` (default) and `continuous_125`.

The 125% continuous-load rule always applies to the charger's branch circuit: a 48 A charger needs a 60 A circuit. That is a separate check from service capacity.

## 6. Load management

A listed energy management or power control system that limits the charger's current lets the load be taken at the controlled setpoint instead of nameplate (625.42 with 750.30 in 2020-2023; 120.7 with 625.42 in 2026). Enter it as `ems_limit_amps`. The 7,200 VA minimum is not applied to a managed setpoint. This is frequently the cheapest way to avoid a service upgrade, and it is worth offering whenever a job fails by less than the charger's own load.

A charger with a user-adjustable current setting is not the same thing; most AHJs want the setting locked or the nameplate used.

## 7. Confidence in each rule

| Rule | Basis | Confidence |
|---|---|---|
| 220.82 tiers, unit loads, six HVAC candidates (2017-2023) | long-standing, widely taught | high |
| 220.83 (A)/(B) (2017-2023) | long-standing; HVAC-in-pool under (A) is disputed | high, with the noted dispute |
| 220.87 125% and data conditions | long-standing | high |
| 220.57 7,200 VA minimum (2023) | several independent sources | high |
| 2026: Article 120, 2 VA, 8 kVA, EVSE at 100% in 120.82 | several independent change summaries agree | medium-high |
| 2026: Table 120.83 factors of 80 / 80 / 50 | two sources agree, one conflicts | medium |
| 2026: 120.87 subtraction of removed loads | one source | low |

None of this was checked against the code book text. Anyone submitting for a permit should confirm the cited sections in the adopted edition.
