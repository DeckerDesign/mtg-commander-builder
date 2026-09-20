# WORKFLOW — top to bottom

The canonical process for turning a new pilot into a working deck-building system, and
then turning intents into exported decks. Design decisions are in `docs/adr/`; language
is in `CONTEXT.md`; power-level rules live in `profile/power-level-notes.md` and are
authoritative over everything here.

Each phase is a **skill** (`.claude/skills/`). Invoke them in order.

## 0. Setup

```bash
pip install -r requirements.txt
```

The repo ships a fictional example (Aesi, Tyrant of Gyre Strait landfall build) so it
runs on clone. Onboarding replaces it with the real pilot's data.

## 1. `intake` — raw material → vetted Profile facts

Tell the agent your commander(s), rough budget, playgroup meta, and preferred platforms.
The skill fetches live data from Scryfall (card legality, color identity, price) and
EDHREC (archetype archetypes, popular cards, synergy scores), then proposes extracted
content as **discrete items you vet one by one** (accept / edit / reject). Nothing enters
the Profile unvetted; nothing is invented.

What it proposes:
- **Identity** — pilot name, preferred export platform, meta power level.
- **Commander overlays** — one per commander: archetype, key synergies, recommended
  packages, default power level.
- **Starter packages** — ramp, draw, removal starters for the identified color identity.
- **Cardpool seed** — prompt the pilot to list owned cards (or paste an existing decklist).

## 2. `commander-grill` — power-level notes + playstyle

A one-question-at-a-time grilling session that builds the two things documents can't provide:

- **Power-level notes** — commander by commander, the agent probes and *you defend*: "Your
  Aesi list has Rhystic Study and Oracle of Mul Daya — are you playing this at a 7 or an 8?
  Would you add Mystical Tutor?" Graded: CEDH / optimized / focused / casual / jank.
- **Playstyle note** — what you enjoy playing: archetypes, win conditions, what you hate at
  the table, your meta's expectations, preferred game length.

## 3. `build-library` — seed packages against 3-4 target commanders

Give the skill 3-4 commanders you want to build (or are already playing). It **iteratively
suggests** candidate package cards — ramp slots, draw slots, removal, win-cons, synergies —
and you **vet each** (accept / edit / reject / replace), until you judge the library rich
enough to brew from. Sources: Scryfall search + EDHREC top-card data.

## 4. `brew` — one intent → a tuned deck

Describe your intent (e.g. "Aesi landfall combo, focused 7, ~$400 budget"). The skill:

1. Checks `decks/` for a duplicate commander + archetype and stops if found.
2. Parses the intent and scores **commander fit** (Strong / Adequate / Weak).
3. Drafts `decks/NNN_<commander-archetype>/` (`intent.md` + `deck_selection.yaml`) with
   honest gaps and an acquisition list.
4. **REVIEW GATE** — shows the real resolved deck (`python engine/preview.py decks/<dir>`)
   including mana curve, package breakdown, synergy density, power level estimate, and a
   playability rating. Flags cards not in the cardpool as acquisitions with prices.
5. Iterates on feedback.
6. On approval, exports: `python engine/apply.py decks/<dir>` — validates hard rules,
   then writes export files in all configured formats (Moxfield, text, Archidekt).

### The hard rules (checks enforce; never add a card just to hit 100)

| Failure | Fix |
|---|---|
| Deck is not exactly 100 cards | Add/remove from the lowest-priority package |
| A card violates color identity | Swap for an in-color equivalent |
| A card is banned | Replace immediately |
| Singleton violated | Remove the duplicate |
| Power level claim exceeds notes | Lower the claim or upgrade the list honestly |

## `tune` — adjusting after playtesting (maintenance, any time)

When a built deck underperforms and the fix is a **configuration change** (swap a ramp
package card, add a package category, adjust power level target) rather than a one-off
tweak, invoke `tune`. It reads your feedback ("too slow on turn 3", "no answer to
graveyards", "curve too high"), measures the current config, maps the fix to a concrete
change in the commander overlay or package files, rebuilds, and re-runs preview. The change
sticks for all future brews of that commander.

## Growing the library

The library grows only through the review gate: when an intent needs a new synergy card or
a new package slot, add it to `profile/` **after approval**, and only if it survives the
power-level notes and cardpool constraints.

## Deck records vs frozen applications

Unlike the job tool, deck records are **living references** — you update them as you tune
the physical deck. A `deck_selection.yaml` is the source of truth for what the deck
*should* be; the physical deck may lag behind. Use `brew` to generate an update export
when the two diverge.
