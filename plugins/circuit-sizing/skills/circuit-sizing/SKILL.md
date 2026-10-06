---
name: circuit-sizing
description: Electrical circuit sizing with code-cited worksheets - wire size, breaker size, equipment ground, voltage drop, conduit fill and box fill, from NEC ampacity tables with temperature and bundling corrections. Use this whenever someone asks what size wire or breaker a load needs ("what gauge for a 50 amp circuit", "wire size for a subpanel 150 feet away", "can I put a 30 amp breaker on 12 gauge"), asks about voltage drop on a long run, how many wires fit in a conduit, what size conduit to pull, whether a box is big enough for its wires and devices, or what circuit an air conditioner, heat pump or mini split needs from its nameplate MCA and MOCP. Use it for electricians, apprentices and homeowners, and even when they only describe the job (an EV charger, a shed, a hot tub, a range, a condenser) without naming the calculation. Not for whole-house service load calculations (use residential-load-calc), motors sized from horsepower, or anything over 600 A.
---

# Circuit sizing

Answers the four sizing questions that come up on almost every circuit: what conductor and breaker, how much voltage drop, what conduit, what box. The numbers come from `scripts/circuit_calc.py`, never from memory or mental arithmetic.

## Why the script does the work

These answers come from tables, and a table value remembered slightly wrong produces an undersized wire that overheats inside a wall. The script holds the tables, applies the corrections in the right order, cites the section for every step, and flags the assumptions that change the answer. If a case is outside what it handles, say so instead of estimating.

## Workflow

### 1. Work out which calculation the user needs

| They ask | `calc` |
|---|---|
| What wire or breaker for this load; is this wire OK on this breaker | `wire` |
| Wire and breaker for an air conditioner, heat pump, mini split or other unit with MCA and MOCP on its nameplate | `nameplate` |
| Voltage drop on a run they have already chosen | `voltage_drop` |
| What size conduit, or how many wires fit in one | `conduit_fill` |
| Is this box big enough; what box do I need | `box_fill` |

A job often needs several, and one run can do them together so the user gets one worksheet with one notice:

- Wire plus its conduit: add `"conduit": {"raceway": "emt", "insulation": "thhn", "neutral": false}` to a `wire` or `nameplate` job. The script sizes the raceway for the conductors and ground it just chose. Use `"extra"` inside it for other conductors sharing the raceway.
- Unrelated questions in one message (a conduit count and a box check): wrap them as `{"job": "title", "jobs": [ {...}, {...} ]}`.

### 2. Get the inputs

Run `python scripts/circuit_calc.py --template <calc>` to see the input shape for each. What matters most:

**wire**
- Load in amps, and whether it is continuous (expected to run three hours or more: EV charging, electric heat, lighting in a store). If the user gives watts, divide by volts. For a mixed load give `continuous_amps` and `noncontinuous_amps`.
- Voltage and phase. One-way length in feet, if they know it; without it the voltage-drop check is skipped.
- Copper or aluminum. Wiring method: `nm` for NM cable (Romex), `raceway` for individual conductors in conduit or for cable types rated at their full temperature.
- Conditions that reduce ampacity: ambient temperature above 30 C (attics, rooftops, boiler rooms) and more than three current-carrying conductors together.
- Two different temperature ratings, easy to mix up. `insulation` is the wire type (`thhn`, `thwn-2`, `xhhw-2`, `thwn`...) and decides which ampacity column the corrections start from; give the type and let the script look up the rating. `terminal_temp` is the rating of the lugs and breaker: 75 unless they tell you the equipment is marked 60 C. When a user says "75C lugs", that is `terminal_temp`, not the wire. The worksheet reports what changes at 60 C.
- If they already have a breaker size in mind, pass it as `breaker_a` and the script checks the conductor against it.
- If wire is already installed and the question is whether it can stay, pass it as `existing_size`. The worksheet then gives a plain verdict on it, which is the line the user actually asked for.
- Leave `max_voltage_drop_pct` at 3 unless the user names a different target. 3% is the usual figure for one feeder or one branch circuit; 5% is for the feeder and branch together, so raising it for a single run hides a problem.

**nameplate**: `mca` (minimum circuit ampacity) and `mocp` (maximum overcurrent device, sometimes "max fuse or breaker") read off the unit's own nameplate, plus the same voltage, length, material and wiring inputs as `wire`. On a changeout, also pass the wire and breaker that are already there as `existing_size` and `breaker_a`; the worksheet says whether each can stay. These units follow different rules from general loads: the nameplate already includes the 125% allowance, and the breaker may be larger than the wire would normally allow. Running one through `wire` gives the wrong answer in both directions, so ask for the nameplate values instead of guessing from tonnage. If the user only has a catalog sheet, use it and say the unit's nameplate governs.

**voltage_drop** and any run with a length: `raceway_material` (`steel`, `pvc` or `aluminum`; default steel, the most conservative) only matters for 1/0 AWG and larger, where reactance adds to the drop.

**conduit_fill**: raceway type (`emt`, `imc`, `rmc`, `pvc40`, `pvc80`), every conductor in it including grounds, with insulation type (`thhn` covers THHN/THWN-2; `xhhw`). Give `trade_size` to check a size they have; leave it out to get the minimum. When the question is how many wires can go in a conduit, also give `breaker_a` (the circuits' breaker size): fill is rarely the real limit, and the worksheet then shows how many current-carrying conductors the wire can share the raceway with before derating drops it below the breaker.

**box_fill**: count of insulated conductors by size (each one entering and terminating or splicing counts once; pigtails don't count), the equipment grounds, whether the box has internal cable clamps, and each device with the largest wire on it. Give `box_volume_in3` if they know the box. Give the code `edition`, because the rule for counting grounds changed in 2020.

Ask for what is missing in one short message. Where a sensible default exists (30 C ambient, three or fewer conductors, copper, 75 C terminals), use it and say so, instead of interrogating the user. Never invent the load.

### 3. Run it

```
python scripts/circuit_calc.py job.json
```

It prints a markdown worksheet. `--format json` gives the numbers for chaining one calculation into the next.

### 4. Report

Order the reply so the worksheet comes last: the answer in one line (conductor, breaker, ground, conduit), then your few lines of commentary, then the worksheet exactly as printed. The worksheet ends with the Notice, so the reply ends with it too, and nothing you write gets stranded below the fine print. Paste the worksheet once; don't also attach or repeat it.

Keep what you add around the worksheet short, because the worksheet already carries the steps, the checks and the notice, and an electrician asking a quick question does not want two pages:

- **Don't restate the worksheet.** Its "Check before relying on this" items are already in front of the reader. Mention one in your own words only when it is the thing most likely to change this user's answer (usually the 60 C termination note or a voltage-drop upsize), and say why it matters for their job.
- **Say what would change the answer**, in a line or two: which is a code minimum and which is a recommendation, and the one or two assumptions you had to make.
- **Add practical points only when they bear on this job**: the larger wire must fit the lugs; aluminum needs terminals rated for it; a long pull may want the next conduit size. Three is plenty.
- **Match the reader.** Someone who writes "#12 THHN", "MCA" or "whip" is in the trade: no glossary, no permit lecture beyond the closing line. For a homeowner, explain a term the first time it appears (AWG is wire gauge, smaller number is thicker wire) and keep it plain.

For a run to a shed, detached garage or other outbuilding, read `references/outbuildings.md` first: the cable type, burial depth and disconnect matter as much as the wire size, and a homeowner asking about gauge usually has not thought of them.

### 5. Disclaimers that stay in every answer

An undersized conductor or an overfilled box is a fire risk, and the tables here were entered from public sources and cross-checked against independent published copies, not against the code book itself. So every answer carries:

- **The Notice block.** The worksheet ends with a "Notice" section. Keep it word for word whenever the worksheet is shown or saved, and don't add a closing sentence of your own that says the same thing again. If you answer without the worksheet, say the same in a sentence: calculation aid only, not verified against the code book, the adopted edition, local amendments and the inspector govern.
- **It is not an approval.** Only the authority having jurisdiction decides what is accepted.
- **Licensed work.** For a homeowner, say that new circuits need a permit in most places and that work inside a panel is a job for a licensed electrician. Don't walk a homeowner through working in a live panel.
- **No talking the answer down.** If the calculation says the wire is too small for the breaker, don't help rationalize keeping it ("it's only a short run", "it rarely runs at full load"). The fix is a larger wire or a smaller breaker.

Don't add more warnings than these; a wall of caveats gets skipped.

## Scope and limits

- Copper and aluminum, 14 AWG to 600 kcmil, single conductors per phase, up to 600 A.
- General loads through `wire`; air-conditioning and heat-pump equipment through `nameplate`. Motors without an MCA marking (sized from the full-load current tables in Article 430) and welders (630) are not covered; say so and don't force them through either calculation.
- Voltage drop uses the larger of direct-current resistance and effective impedance at 0.85 power factor, so it stays conservative from 14 AWG to 600 kcmil. Loads with a much lower power factor drop more; the worksheet says so when it matters.
- Code editions: the tables and rules here are the same in the 2017, 2020 and 2023 editions (section numbers shifted in 2020). Published summaries of the 2026 edition report the core tables unchanged; its additions (16 AWG ampacity, a 40 A allowance for 10 AWG on some equipment circuits) are not implemented. Box fill takes an `edition` because the ground-counting rule changed in 2020.
- Conduit fill covers EMT, IMC, RMC and PVC Schedule 40 and 80 up to trade size 4, with THHN/THWN-2 and XHHW conductors. Other raceways and insulation types are not in the tables.
- Box fill covers 18 to 6 AWG. Boxes with 4 AWG and larger conductors are sized by dimensions (314.28), not volume.
- The code is copyrighted. Cite section and table numbers and explain in your own words; don't quote code text.

Read `references/method-notes.md` when the user asks why a step was applied, when an inspector disputes a line, or when a case falls near the edges above.
