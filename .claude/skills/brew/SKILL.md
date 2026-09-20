---
name: brew
description: Turn one play intent into a tuned, export-ready 100-card Commander deck by SELECTING from the vetted package library — with honest power-level feedback, a playability rating, and a review gate showing the real resolved deck before anything exports. The production cycle. Use when the user describes a deck they want to build, or says "brew this", "build me a deck", "make me an Aesi list", "I want to build X".
---

# brew — one intent in, a tuned deck out

Phase 4, the production cycle. `brew(intent)` builds from the vetted library into a full
Commander deck. It **selects** vetted cards; the only generated prose is the strategy hook
description. **It shows the real resolved deck and waits for approval before exporting.**

## Before anything: read the Profile

Read `profile/power-level-notes.md` (authoritative on power level and budget), `profile/playstyle.md`
(what card choices feel right), `profile/layout.yaml` (target counts per package, deck size),
and skim `profile/commanders/*.yaml`. Read `profile/cardpool.yaml` to know what needs acquiring.

## Steps

**1. Check for a duplicate.** Look in `decks/` for the same commander + archetype. If found,
say so and offer to update the existing record instead of creating a duplicate.

**2. Parse the intent** — commander, archetype/strategy goal, target power level, budget constraint.

**3. Score commander fit** — Strong / Adequate / Weak. Weak means the stated strategy fights
the commander's grain: using a combo commander for a value build, or a voltron commander for
a group-hug build. Strong/Adequate → proceed. Weak → propose a better-aligned commander or
a strategy pivot; don't force-fit silently.

**4. Draft the selection.** Create `decks/NNN_<commander-archetype>/` (NNN = next folder
number), with `intent.md` and `deck_selection.yaml`. Set commander, archetype, package
selections (which cards from each package), synergy picks, land base, strategy hook, and
power level claim. Record honest gaps under `gaps` — never claim past the power-level notes.
Flag any card not in `profile/cardpool.yaml` under `acquire`.

**5. REVIEW GATE — show, do not export.** Run:
`python engine/preview.py decks/<dir>`
Present the real resolved deck: commander + fit verdict, full card list grouped by package,
mana curve chart (ASCII), package breakdown (ramp count, draw count, removal count, etc.),
playability rating (0-100 → 1-10 scale), average CMC, power level estimate, and acquisition
list with prices. Then **stop and wait.** Never export before approval.

**6. Iterate** on `deck_selection.yaml` and re-preview until the user approves.

**7. Export — only on approval:**
`python engine/apply.py decks/<dir>`
It validates the hard rules, then writes export files for all configured formats. Never add
filler cards to hit 100 — fix it with a purposeful card from the library.

| Failure | Fix |
|---|---|
| Deck is not 100 cards | Add/remove the lowest-priority card in the weakest package |
| Color identity violation | Swap for an in-color equivalent from the package |
| Banned card | Replace immediately with the next-best option from the library |
| Singleton violated | Remove the duplicate; keep the better copy |
| Power level claim > notes | Lower the claim, or add the cards that justify the higher level |

**8. Grow the library only through the gate.** If the intent needed a new synergy card or
a new package slot, add it to `profile/` after approval — never silently, only with cards
that survive the power-level notes and budget constraints.

## Playability rating breakdown

The rating is honest. It grades the deck as-built, not as aspired-to:

| Dimension | Points | What it checks |
|---|---|---|
| Mana curve health | 0-25 | Ramp ≥ target, avg CMC ≤ threshold, early play density |
| Interaction density | 0-25 | Removal + counterspells + protection count vs target |
| Synergy density | 0-25 | Cards that work with the commander / total nonland cards |
| Consistency | 0-25 | Tutor count, redundancy in key packages, card quality |

Total maps: 90-100 → 10 (CEDH), 75-89 → 8-9 (optimized), 55-74 → 6-7 (focused),
35-54 → 4-5 (casual), <35 → 1-3 (jank).

## Once sleeved, treat as a living reference

A built deck record is the source of truth for what the physical deck *should* be. When the
physical deck diverges (you swapped a card at the store), update `deck_selection.yaml` and
re-export. Use `tune` for systematic changes after playtesting.
