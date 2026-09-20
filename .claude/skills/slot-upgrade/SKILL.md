---
name: slot-upgrade
description: Find the weakest cards in a deck's package slots and suggest concrete replacements. Scores each incumbent on CMC vs package ideal, EDHREC rank, and archetype keyword fit, then searches Scryfall for better alternatives. Use when the user says "upgrade my deck", "find weak cards", "what should I cut", "improve my ramp", "what's the worst card in [slot]", or after a playtest surfaces issues.
---

# slot-upgrade — find weak incumbents and suggest replacements

Identifies the most replaceable cards in the deck by slot, then searches Scryfall
for alternatives that do the job better: lower CMC, higher synergy, or budget-friendlier.
Designed to run after `/playtest` or whenever the user wants to tighten the 100.

## Step 1 — Read the profile and playtest context

Read `profile/power-level-notes.md`, `profile/playstyle.md`, and any recent playtest
output in the conversation. Issues the playtest surfaced should inform which packages
to focus on first.

## Step 2 — Run the upgrade finder

**Auto mode** — scan all package slots, surface the top 3 weakest cards:
```
python engine/slot_upgrade.py decks/<dir> --auto
```

**Package mode** — scan a specific slot:
```
python engine/slot_upgrade.py decks/<dir> --package ramp --top 5
```

**Single card mode** — find replacements for a specific card:
```
python engine/slot_upgrade.py decks/<dir> --card "Solemn Simulacrum"
```

With budget filter:
```
python engine/slot_upgrade.py decks/<dir> --auto --budget 5
```

## Step 3 — Enrich with playtest data

If a recent playtest surfaced specific issues (e.g., "low interaction at turn 5"),
link the upgrade suggestion back to it:

> "The playtest showed interaction available at only 32% of threat windows.
> Solemn Simulacrum is the weakest removal-adjacent card — here are 3 instant-speed
> upgrades that would help that window."

## Step 4 — Review gate

Present results as proposals. For each suggested swap:
- Name the card being cut and why it's weak
- Name the replacement and why it's better
- Show CMC, price, EDHREC rank side-by-side

Stop. Wait for the user to accept, reject, or ask for alternatives.

## Step 5 — Apply approved swaps

For each approved swap:
1. Edit `deck_selection.yaml` — remove the cut card, add the replacement to its slot.
2. Re-run checks: `python engine/checks.py decks/<dir>`
3. Re-run preview: `python engine/preview.py decks/<dir>`
4. If playtest issues were the trigger, re-run playtest to confirm improvement:
   `python engine/playtest.py decks/<dir> --games 5 --auto-pod`

## Hard limits

- **Never suggest cards that violate `profile/power-level-notes.md`** — no infinite
  combos, no stax, no power tier above what the notes allow.
- **Never suggest cards outside the commander's color identity.**
- **Playstyle alignment** — no stax pieces, no land destruction as strategy.
- **Budget awareness** — flag cards above the pilot's per-card cap and always offer
  a budget alternative.
- **Never auto-write** to `deck_selection.yaml` — every change is user-approved.
