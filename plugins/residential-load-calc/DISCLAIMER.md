# Disclaimer: residential-load-calc

Read this before relying on anything this plugin produces.

## What this is

A calculation aid. It applies published load-calculation methods to the numbers you give it and prints a worksheet. It is a starting point for a conversation with a licensed electrician and the local building department.

## What this is not

- **Not professional advice.** Nothing here is engineering, legal, safety or code-compliance advice. The author is not your electrician, engineer or inspector.
- **Not the code.** The rules were implemented from public summaries of the National Electrical Code. They were not verified against the code text. Support for the 2026 edition is provisional and is flagged on every run. Always confirm the cited sections in the edition your jurisdiction has adopted, including local amendments.
- **Not a permit or an approval.** Only the authority having jurisdiction decides what is accepted. A worksheet that says "fits" does not authorize any installation.
- **Not a site inspection.** The result is only as good as the inputs. Nameplate ratings, the true service rating (the lowest of main breaker, service conductors and panel bus), panel condition and physical space all have to be verified on site.

## Safety

Electrical work can cause fire, serious injury and death. Service conductors remain live with the main breaker off. Installation work requires a permit and, in most places, a licensed electrician. Do not open a panel or work on a service because of anything this plugin tells you.

## No warranty, no liability

The plugin is provided "as is", without warranty of any kind, express or implied, including fitness for a particular purpose and accuracy of results. To the fullest extent permitted by law, the author is not liable for any loss, damage, injury or cost arising from its use. You use it at your own risk and are responsible for checking its output. See `LICENSE` for the full terms.

## AI output

Claude writes the explanation around the worksheet. AI models can misread a request, pick the wrong method or state something incorrect with confidence. The numbers come from the bundled script, but the choice of inputs and the commentary do not. Review both.

## Trademarks

NEC and National Electrical Code are registered trademarks of the National Fire Protection Association (NFPA). This project is not affiliated with, sponsored by or endorsed by NFPA. It cites section numbers and describes methods in its own words; it does not reproduce code text.
