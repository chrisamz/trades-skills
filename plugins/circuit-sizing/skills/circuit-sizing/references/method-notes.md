# Method notes

What `circuit_calc.py` implements, in what order, and how far each part can be trusted. Section numbers follow the 2020 and 2023 NEC; a few were numbered differently in earlier editions (the ampacity table was Table 310.15(B)(16) through 2017).

## Contents

1. Conductor and overcurrent sizing, including air-conditioning equipment
2. Voltage drop
3. Conduit fill
4. Box fill
5. Where the table values came from, and the 2026 edition
6. Confidence
7. How the skill was tested

## 1. Conductor and overcurrent sizing, including air-conditioning equipment

The script picks the smallest conductor that passes every test below.

1. **Sizing current.** 125% of the continuous load plus 100% of the noncontinuous load (210.19(A), 210.20(A); 215.2 and 215.3 for feeders). A load is continuous when its maximum current is expected for three hours or more.
2. **Overcurrent device.** The next standard rating at or above the sizing current (240.6(A)), unless the user supplies one.
3. **Termination test.** The conductor's ampacity in the column for the termination temperature must be at least the sizing current (110.14(C)). Terminals on equipment rated 100 A or less are treated as 60 C unless marked 75 C; nearly all current breakers and panels are marked 60/75 C, so the script defaults to 75 C and reports the 60 C answer alongside.
4. **Conditions-of-use test.** The ampacity in the insulation's own column, times the ambient correction, times the adjustment for more than three current-carrying conductors, must be at least the actual load (310.15). Corrections are taken from the 90 C value for 90 C insulation even when terminations limit the final ampacity to a lower column.
5. **Protection test.** The device must not exceed the conductor's ampacity (the lower of the corrected value and the termination value), except that the next standard size up is allowed when the ampacity falls between standard ratings (240.4(B)).
6. **Small-conductor limits.** 14 AWG copper 15 A, 12 AWG 20 A, 10 AWG 30 A; 12 AWG aluminum 15 A, 10 AWG 25 A (240.4(D)).

NM cable: ampacity is limited to the 60 C column, and corrections are applied to the 90 C value (334.80). Since 60 C governs termination anyway, `wiring: nm` forces both.

Equipment ground: from the device rating (Table 250.122), never larger than the circuit conductors (250.122(A)). When the ungrounded conductors are increased for voltage drop, the ground is increased in the same proportion by circular-mil area (250.122(B)).

**Air-conditioning and heat-pump equipment (`nameplate`).** Equipment with a hermetic compressor is marked with a minimum circuit ampacity (MCA) and a maximum overcurrent device (MOCP) (440.4(B)). The MCA already contains 125% of the largest motor plus the other loads (440.33, 440.35), so the conductor is sized to the MCA as marked: termination-column ampacity and corrected ampacity must each be at least the MCA, with nothing more added. The device may be as large as the MOCP (440.22), and the small-conductor limits do not apply (240.4(G)), so a 40 A breaker on 12 AWG copper can be correct. The script picks the largest standard rating not over the MOCP; a smaller one is allowed if the unit starts on it. Inspectors unfamiliar with this ask about it, which is why the worksheet tells the user to have the nameplate at hand.

Not handled: motors sized from horsepower and the full-load current tables (430), welders (630), fixed electric space heating's own rules (424), tap rules (240.21), parallel conductors (310.10(G)), and the dwelling service and feeder table (310.12).

## 2. Voltage drop

Single-phase: drop = 2 x length x resistance x current / 1,000. Three-phase: 1.732 in place of 2. Length is one way, in feet; resistance is ohms per 1,000 ft from Chapter 9, Table 8 (stranded, uncoated copper or aluminum, 75 C).

The 3% branch-circuit and 5% feeder-plus-branch figures are recommendations in informational notes to 210.19 and 215.2. They are not enforceable unless a specific rule or a local amendment says so (some energy codes do).

Direct-current resistance is a good approximation through about 1 AWG. For 1/0 AWG and larger on alternating current, inductive reactance becomes significant and the true drop is higher. Chapter 9, Table 9 gives an effective impedance at 0.85 power factor for conductors in PVC, aluminum and steel conduit. The script uses the larger of the Table 8 resistance and the Table 9 effective impedance for the conduit material given (steel when not stated, the highest of the three). For small conductors the direct-current value is the larger one, which is the usual conservative convention; from 1/0 AWG up the effective impedance takes over. The worksheet names which table the number came from.

Effective impedance assumes 0.85 power factor. A load with a much lower power factor drops more, and Table 9's separate R and X values are needed to compute it; the script does not do that. For NM and other cables the script uses the PVC column, since there is no steel around the conductors.

The current used is the actual load, not the breaker rating. Using the breaker rating is a more conservative convention some designers prefer; pass that current as `load_amps` in a `voltage_drop` run to see it.

## 3. Conduit fill

Sum the insulated cross-sectional areas of all conductors (Chapter 9, Table 5) and compare with the raceway's internal area (Table 4) times the limit from Table 1: 53% for one conductor, 31% for two, 40% for more than two. A nipple 24 in. or shorter may be filled to 60% (Note 4).

When every conductor is the same, the script also reports the most that fit, rounding up when the fraction is 0.8 or more (Note 7). That rounding is why published count tables sometimes show one more conductor than plain division gives.

One place the script is stricter than the published count tables: those tables apply the 40% limit to every count, so they sometimes show two conductors where the two-conductor limit of 31% would not allow them (two 6 AWG THHN in 1/2 EMT, for example). The script applies 31% to a count of two and 53% to a count of one, and reports one conductor in that case. An inspector may accept the published table; the script's answer is the conservative one.

Equipment grounds count toward fill. A bare ground's area comes from Table 8 and is smaller than an insulated conductor's; entering grounds as insulated is conservative.

Fill and ampacity are separate. Passing fill says the conductors can be pulled without damage; it says nothing about heat. More than three current-carrying conductors in a raceway reduces ampacity (310.15(C)(1)).

## 4. Box fill

Required volume is the sum of allowances, each one conductor's worth of volume from Table 314.16(B)(1) (314.16(B)):

- each conductor that enters and is spliced or terminated: one, at its own size
- each conductor that passes through unbroken: one (two if the loop is long enough to be cut and spliced)
- internal cable clamps, any number: one, at the largest conductor
- each type of fixture stud or hickey: one, at the largest conductor
- each device yoke: two, at the largest conductor connected to it; a device wider than a single gang takes two per gang it needs
- equipment grounds: through the 2017 edition, all of them together count as one at the largest ground. From 2020 on, the first four count as one and each one beyond four adds a quarter.

Pigtails and jumpers that begin and end in the box are not counted. Conductors 4 AWG and larger are outside this method; boxes for them are sized by their dimensions (314.28).

The list of standard metal boxes comes from Table 314.16(A). Nonmetallic boxes carry a marked volume, which should be used instead.

## 5. Where the table values came from

The tables in the script were entered from the commonly published values and then checked against independent published copies. Nothing was checked against the code book itself.

| Table in the script | Checked against | Result |
|---|---|---|
| Ampacity, copper and aluminum, 14 AWG to 600 kcmil, all three columns | A published copy of the 2020 table (lugsdirect.com) | Every cell matches |
| Ambient correction factors, all bands | Elliott Electric Supply reference table, 2020 edition | Every cell matches |
| Conduit internal areas, trade sizes 1/2 to 2, EMT, IMC, RMC, PVC 40, PVC 80; THHN areas 14 AWG to 250 kcmil | Elliott Electric Supply conductor-count tables, 2017 and 2020 editions | The script reproduces every published count of three or more conductors, over 150 cells; this runs as a regression test |
| THHN areas, full column to 500 kcmil | A second published listing | Every value matches |
| Effective impedance (Table 9), 14 AWG to 400 kcmil, copper and aluminum, three conduit materials | A scanned code page (2007 California Electrical Code, same table) | Every cell matches |
| Direct-current resistance (Table 8) | Cross-check against the alternating-current resistance column of the Table 9 scan | Within rounding for every size |
| Box volume allowances and the 2020 change for grounds | Two published articles | Match |
| Equipment ground table | Entered from memory; consistent with published examples | Not compared cell by cell |

Still not independently checked: conduit areas for trade sizes 2-1/2 to 4, XHHW areas above 6 AWG, effective impedance for 500 and 600 kcmil (computed from R and X, not read from a copy), and the list of standard box volumes. Third-party ampacity charts found during checking disagreed with each other in places because some still carry values from before the 2011 revision (3 AWG copper at 90 C was 110 A and is 115 A; 1 AWG was 150 A and is 145 A; 8 AWG aluminum at 60 C was 30 A and is 35 A; 6 AWG aluminum at 90 C was 60 A and is 55 A). The script uses the current values.

A regression test also checks that every ampacity column rises with conductor size and that the two resistance tables agree with each other, so a mistyped cell in either would fail the tests.

### 2026 edition

Published summaries of the 2026 edition report that the core ampacity values, the conduit fill limits and the equipment ground table are unchanged from 2023. Reported changes that the script does not implement: ampacity values for 16 AWG copper, a 40 A allowance for 10 AWG copper on certain equipment circuits (240.4(D)), a revised rule for equipment grounds in parallel raceways (250.122(F)), and clarified wording that splicing connectors and small fittings need no box-fill allowance, which matches what the script already does. These come from change summaries, not the code book.

## 6. Confidence

| Part | Confidence |
|---|---|
| Sizing order (termination, conditions of use, protection, small-conductor limits) | high |
| Ampacity tables, both metals; ambient correction; bundling adjustment | high, cell-checked |
| Conduit and THHN areas through trade size 2 | high, cell-checked |
| Voltage drop: resistance and effective impedance through 400 kcmil | high, cell-checked |
| Box fill rules, including the 2020 change for grounds | high |
| Nameplate method for air-conditioning equipment | high for the method; it relies on the user reading the nameplate correctly |
| Conduit areas above trade size 2; XHHW areas above 6 AWG; 500 and 600 kcmil impedance; standard box list | medium |
| 2026 edition | summaries only; additions not implemented |

| `outbuildings.md` (burial depths, disconnect, grounding at a detached building) | medium; written from general knowledge and not compared with a published copy |

Confirm the cited tables in the adopted edition before relying on a result.

## 7. How the skill was tested

Each test prompt was run once with the skill and once without, and graded by hand against a short list of checks. On the strongest model the skill changed little: answers without it were already correct on every numeric check. On a small model the difference was large: across four prompts (a condenser changeout, stacked rooftop derating, an aluminum feeder to a detached garage, and voltage drop on a long 3/0 run), answers without the skill passed 3 of 19 checks and answers with it passed 18 of 19. The one miss came from a lug rating being entered as the wire's rating, which the script now warns about. These are single runs, so treat the figures as indicative.
