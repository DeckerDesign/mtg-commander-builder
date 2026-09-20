# mtg-commander-builder

A system that turns a play intent into a tuned, export-ready Commander deck for **one pilot**,
grounded in what they can actually pilot and afford. An AI agent reads the intent and chooses
the cards; a deterministic Engine validates and exports from the pilot's Profile.

## Language

**Engine**:
The person-agnostic tooling in `engine/`: resolve, validate, export. Hardcodes nothing about
any individual — every personal fact and every layout choice is read from the **Profile**.
_Avoid_: mixing with **Library**.

**Profile**:
Everything that is *the pilot*, in `profile/`: **identity**, **playstyle note**, **power-level
notes**, **card packages**, **commander overlays**, **layout config**, and **cardpool**. Ships
as a fictional Aesi example; **onboarding** fills it. The Engine reads it; it never reads the
Engine.

**Library** (narrowed):
The pilot's vetted, selectable *content* — the card packages (ramp, draw, removal, win-cons,
synergies) and **Commander overlays** the agent selects from. A subset of the **Profile**.

**Package**:
A named, function-scoped collection of vetted cards the agent selects from: `ramp`, `draw`,
`removal`, `protection`, `wincons`, `synergy`. Packages live in `profile/packages/<name>.yaml`.
A commander overlay may override or extend any package for that commander.

**Commander overlay** (`profile/commanders/<slug>.yaml`):
Per-commander config: archetype, key synergy cards, recommended packages, default power level,
win condition strategy, and the selection defaults the agent starts from. Categories in the job
tool; commanders here.

**Power-level notes** (`profile/power-level-notes.md`):
The authoritative record of what the pilot honestly plays at and can afford, graded per
commander and per claim (CEDH / optimized / focused / casual / jank). No deck may be exported
claiming a higher power level than what is defensible here. Built by `commander-grill`. Like
`honesty-notes.md` in the job tool — the linchpin that keeps outputs credible.
_Avoid_: overstating power level to fit into a higher-powered meta group.

**Playstyle note** (`profile/playstyle.md`):
A short, distilled artifact — how the pilot likes to play. Archetypes they enjoy (combo, value,
aggro, stax, politics), what they hate (infinite combos? land destruction?), their learning
goals, preferred game length. **Preference only**; power-level notes own objective power claims.
Governs which cards feel right, not which are mathematically strongest.

**Cardpool** (`profile/cardpool.yaml`):
Cards the pilot owns, wants, or is willing to proxy. The engine compares a resolved deck
against it to produce an acquisition list and budget estimate. If a selected card is not in
the cardpool, it is flagged as a buy/acquire item.

**Layout config** (`profile/layout.yaml`):
The per-pilot deck construction contract: total deck size (100), target counts per package
category (ramp_count, draw_count, removal_count, etc.), export format preferences, and the
hard-cap budget if set.

**Deck selection** (`deck_selection.yaml`):
The small structured artifact the agent emits per intent: the chosen commander, archetype,
package choices (which cards from each package), synergy picks, strategy hook, power level
claim, and gaps. The agent's entire output; the Engine validates and exports from it.

**Application** → **Deck record**:
One intent in, a tuned 100-card deck out, persisted as a folder under `decks/` (the intent,
the selection config, the exported decklist files) so it is reproducible. Once sleeved and
played, treat it as a reference point, not a frozen record.

**Review gate**:
The mandatory stop where the agent shows the *real resolved deck* (via `engine/preview.py`)
including stats — mana curve, package breakdown, synergy density, power level estimate, gaps,
acquisition list — and waits for approval before exporting. Conversational. Never export first.

**Power level fit**:
The agent's verdict on how well an intent matches the chosen commander: Strong / Adequate /
Weak. Weak means forcing a strategy that fights the commander's natural grain — triggers a
redirect or a new commander proposal instead of forcing it.

**Playability rating**:
A composite score (0–100 → maps to 1–10 power level) across four dimensions: mana curve
health, interaction density, synergy density, and card consistency. Honest — it grades what
the deck actually does, not what the pilot hopes it does.

**Tune**:
Adjusting a commander overlay or package after playtesting — like `format-correction` in the
job tool. Changes the **config**, not one deck's content; applies to all future brews of that
commander.

**The pipeline skills**:
`intake` (commander + playstyle → vetted Profile) → `commander-grill` (power-level notes +
playstyle note) → `build-library` (seed packages against target commanders) → `brew` (one
intent → review gate → export). Plus **`tune`**, a maintenance skill that adjusts commander
overlays and package configs from playtesting feedback.
