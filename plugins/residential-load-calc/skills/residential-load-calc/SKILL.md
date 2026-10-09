---
name: residential-load-calc
description: Residential electrical load calculation and panel capacity check using the NEC optional method (220.82), the existing-dwelling method (220.83) and recorded demand (220.87), including the 2026 NEC Article 120 renumbering. Use this whenever someone asks whether a house service or panel can handle an added load such as an EV charger, heat pump, mini split, electric range, hot tub, tankless water heater, ADU or generator; asks "do I need a service upgrade", "is 100 amp / 200 amp enough", "how many amps is my house using"; needs a load calc for a permit; or gives square footage and appliance nameplates and wants service size. Use it even if they never say "load calculation", and use it for homeowners as well as electricians. Not for commercial or multifamily service sizing, branch-circuit wire sizing or voltage drop.
---

# Residential load calculation

Answers one question: does this dwelling's service or feeder have capacity for its load, and if not, what are the options? The numbers come from `scripts/load_calc.py`, never from mental arithmetic.

## Why the script does the math

Electricians and inspectors distrust AI for exactly this job because a plausible-looking wrong number gets a permit rejected or an overloaded service approved. The script is deterministic, shows every line with its code section, and reports how the answer changes under other defensible readings of the code. Do the arithmetic by hand and you lose all three. If the script cannot handle a case, say so instead of improvising a number.

## Workflow

### 1. Get the inputs

Needed for every job:

- **NEC edition the local authority (AHJ) has adopted**: 2017, 2020, 2023 or 2026. This changes the answer, not just the section numbers (see `references/method-notes.md`). If the user names the edition, use it. If they give only a location, look the adopted edition up with a web search before running, and say where the answer came from; don't answer from memory, because states moved to the 2026 edition on different dates and what you remember is likely out of date. If they give neither, ask. If it still can't be pinned down, run 2023 and 2026, say which was assumed, report whether the result differs, and tell them to confirm with the building department.
- **Service or feeder rating in amps**: the lowest of main breaker, service conductor ampacity and panel bus rating. People usually quote the main breaker; ask if anything suggests the conductors or bus are smaller.
- **What is being added**, with nameplate amps or watts.

Then by method:

- Calculated methods (220.82, 220.83): conditioned floor area in square feet (outside dimensions, excluding garages, open porches and unfinished space not adaptable for future use), and nameplate VA of every fixed appliance, the heating and cooling equipment, and any EV chargers. Two small-appliance circuits and one laundry circuit is the code minimum and a safe default.
- Recorded demand (220.87): the peak demand in kW or amps, where it came from (12 months of utility data, or a 30-day recording), and whether there is solar or battery storage.

Ask for what is missing in one short message. A photo of the panel schedule and nameplates is a fine way for the user to answer. Don't invent nameplate values. If the user wants a rough answer without them, use typical values, label each one "assumed, typical", and say the result is a screening estimate until nameplates are checked.

### 2. Pick the method

| Situation | Method |
|---|---|
| New house, or sizing a whole service from scratch | 220.82 |
| Existing house, adding load, no usage data | 220.83 |
| Existing house, adding load, utility interval data or a recording is available | 220.87, and usually run 220.83 too |
| Service under 100 A, multifamily, commercial, 3-phase | Out of scope. Say so; the standard method (220 Part III) is not implemented |

For an existing house, 220.87 often shows capacity that 220.83 does not, because real houses rarely approach their calculated load. When a calculated method fails, suggest getting the utility data before recommending an upgrade.

### 3. Build the input and run it

Run `python scripts/load_calc.py --template` once to see the input shape, write the job as JSON, then run:

```
python scripts/load_calc.py job.json
```

Mark every added load with `"new": true`. HVAC entries take a `type` of `ac`, `heat_pump`, `supplemental_heat`, `space_heat` or `thermal_storage`; `space_heat` takes `units` (number of separately controlled units) and `supplemental_heat` takes `interlocked` when the compressor cannot run with the strips. An EVSE on a listed load-management system takes `ems_limit_amps`. Appliances accept `va`, `kw`, or `amps` with `volts`.

The script prints a markdown worksheet. Use `--format json` if the numbers feed something else.

### 4. Report

Lead with the verdict in one sentence: calculated amps against the rating, fits or doesn't, and the headroom. If the worksheet says "NOT A VALID RESULT", the method cannot be used for this job as entered: lead with that and the reason it gives, don't describe the amps figure as fitting or not fitting, and rerun with the method it points to (or say the case is out of scope). Then give the worksheet as the script printed it; it is meant to be handed to an inspector, so don't reword the line items or drop the section references.

Then cover, briefly:

- **Other readings.** The worksheet's "Same job under other readings of the code" table already covers every combination an AHJ may require (EV charger inside the demand tiers, at 100% or at 125%; existing heating inside the tiers or at 100%), plus a cross-check under the whole-house method. Don't build extra job files to explore combinations; read them off the table. If the verdict flips under any reading, say that plainly and name the exact question to put to the inspector; it is the most useful thing in the report, because it tells the user what to settle before buying anything.
- **Charger setting and branch circuit.** Where a reading fails, the worksheet lists the largest load-managed charger setting that fits under it. It also gives the minimum branch-circuit rating for a new charger. Pass both along; they are what the electrician prices.
- **Flags.** Relay every item under "Check before relying on this". They are conditions the code attaches to the method, not boilerplate.
- **If it doesn't fit**, the options in rough order of cost: a load-management device or a lower charger setting (the worksheet gives the largest setting that fits; rerun with `ems_limit_amps` to produce the worksheet for it), recorded demand under 220.87 if not tried yet, replacing a large resistance load, then a service upgrade. Give the smallest standard rating the script reports.

### 5. Disclaimers that stay in every answer

People act on these numbers around equipment that can kill them or burn a house down, and the rules here were built from public summaries, not checked against the code text. So every answer carries the following, in plain words and without burying it:

- **The Notice block.** The worksheet ends with a "Notice" section. Keep it word for word whenever the worksheet is shown or saved. If you give a result without the worksheet, say the same things in a sentence or two: calculation aid only, not verified against the code book, the adopted edition, local amendments and the inspector govern.
- **It is not a permit or an approval.** The result says what a load calculation is likely to show. Only the authority having jurisdiction decides what is accepted.
- **Licensed work.** For a homeowner, say that the installation itself needs a permit and, in most places, a licensed electrician, and that they should not open the panel or work on the service themselves. Service conductors stay live even with the main breaker off.
- **Provisional rules.** On any 2026 NEC run, keep the provisional flag.
- **No overriding the verdict.** If the calculation says the load does not fit, don't help the user find a way to make the paperwork pass anyway (leaving loads off, understating nameplates). Offer the legitimate options listed above.

Don't pile on more warnings than these; a wall of caveats gets skipped, and then the ones that matter are not read.

## Scope and limits

- One dwelling unit on a 120/240 V or 208Y/120 V single-phase 3-wire service or feeder.
- Service capacity, plus the minimum circuit rating for a new EV charger. Conductor sizing, other branch circuits, voltage drop and physical panel space are separate checks.
- **Generators:** for an automatic transfer switch carrying the whole house, the load from this calculation is the load the generator must carry unless load shedding is used (702.4). Run the calc and report that number; generator selection beyond that is outside this skill.
- The code is copyrighted. Cite section numbers and explain the method in your own words; don't quote code text.
- 2026 NEC support is provisional: the factors come from published change summaries. The script flags this on every 2026 run; keep the flag in the report.

Read `references/method-notes.md` when the user asks why a factor was used, when an inspector disputes a line, when editions differ, or when a case feels like it falls between methods.
