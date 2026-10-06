# Disclaimer: circuit-sizing

Read this before relying on anything this plugin produces.

## What this is

A calculation aid. It applies published sizing methods and table values to the numbers you give it and prints a worksheet. It is a starting point for a conversation with a licensed electrician and the local building department.

## What this is not

- **Not professional advice.** Nothing here is engineering, legal, safety or code-compliance advice. The author is not your electrician, engineer or inspector.
- **Not the code.** The rules and table values were entered from public sources describing the National Electrical Code. They were cross-checked against independent published copies, not against the code book itself; the record of what was checked is in `skills/circuit-sizing/references/method-notes.md`. The 2026 edition was reviewed only through published change summaries, and its additions are not implemented. Always confirm the cited sections in the edition your jurisdiction has adopted, including local amendments.
- **Not a permit or an approval.** Only the authority having jurisdiction decides what is accepted. A worksheet that says "fits" does not authorize any installation.
- **Not a site inspection.** The result is only as good as the inputs. The actual load, terminal temperature markings, ambient temperature, the number of conductors run together, run length and box markings all have to be verified on site.

## Safety

Electrical work can cause fire, serious injury and death. An undersized conductor or an overfilled box can start a fire long after the work is finished. Service conductors remain live with the main breaker off. Installation work requires a permit and, in most places, a licensed electrician. Do not open a panel or work on a service because of anything this plugin tells you.

## No warranty, no liability

The plugin is provided "as is", without warranty of any kind, express or implied, including fitness for a particular purpose and accuracy of results. To the fullest extent permitted by law, the author is not liable for any loss, damage, injury or cost arising from its use. You use it at your own risk and are responsible for checking its output. See `LICENSE` for the full terms.

## AI output

Claude writes the explanation around the worksheet. AI models can misread a request, pick the wrong method or state something incorrect with confidence. The numbers come from the bundled script, but the choice of inputs and the commentary do not. Review both.

## Table data

The calculator contains numerical values that are widely published and used in electrical work, such as conductor ampacities, resistances, raceway and conductor dimensions and box volume allowances. They are included only so the calculation can run. They are not a copy of the code and are no substitute for it: they omit the notes, exceptions and conditions that govern how the tables may be used. Buy or consult the adopted edition of the code for anything you rely on. If you hold rights in any material here and object to its inclusion, open an issue on the repository and it will be addressed.

## Trademarks

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association (NFPA). This project is not affiliated with, sponsored by or endorsed by NFPA. It cites section numbers and describes methods in its own words; it does not reproduce code text.
