---
name: scan-set
description: Scan a new Magic set release for cards that fit a built deck. Fetches every Commander-legal card from the set in the commander's color identity, scores each for archetype fit, and surfaces the top additions the pilot hasn't already included. Use when the user says "scan [set]", "what's in [set] for me", "new set dropped", "anything good in [set code]", "look at the new cards", or pastes a Scryfall URL.
---

# scan-set — scan a new set for additions

Fetches every Commander-legal card from a set matching the deck's color identity,
scores each for archetype fit using Scryfall + commander overlay data, and returns
the top N cards the deck doesn't already run — organized by package slot.

## Step 1 — Identify the set and deck

Ask the user which set to scan and which deck to scan for (or infer from context).
Accept any of:
- Set code: `MH3`, `BLB`, `OTJ`, `DSK`, `FDN`
- Set name: "Modern Horizons 3", "Bloomburrow"
- Scryfall URL: `https://scryfall.com/sets/mh3` or a full search URL

If given a **Scryfall search URL** (contains `/search?q=`), use that directly:
```
python engine/fetch_scryfall.py --url "https://scryfall.com/search?q=e%3Amh3+ci%3Aug"
```

Otherwise run the set scanner:
```
python engine/scan_set.py <SET_CODE> decks/<dir> --top 12
```

With budget filter:
```
python engine/scan_set.py MH3 decks/<dir> --top 12 --budget 10
```

Filtered to one package slot:
```
python engine/scan_set.py MH3 decks/<dir> --package ramp --top 6
```

## Step 2 — Present results

Show results grouped by package slot. For each card:
- Name, CMC, price, EDHREC rank
- Oracle text (truncated)
- Why it fits: which archetype keyword it hits or which package gap it fills

Cross-reference the deck's existing `gaps:` list in `deck_selection.yaml` — if a new
card directly addresses a listed gap, call that out explicitly.

## Step 3 — Review gate

Stop and wait for the user. Present results as proposals, not changes.
The user accepts, rejects, or modifies each suggestion.

For accepted cards, ask which slot it replaces (if the deck is at 100):
- Suggest the weakest incumbent in that package via `slot_upgrade`:
  `python engine/slot_upgrade.py decks/<dir> --package <pkg> --top 1`

## Step 4 — Apply approved additions

For each approved card:
1. Edit `deck_selection.yaml` — add to the appropriate package list, remove the swapped card.
2. Re-run checks: `python engine/checks.py decks/<dir>`
3. Re-run preview: `python engine/preview.py decks/<dir>`
4. Optionally re-run playtest to confirm the change improved the deck.

## Hard limits

- **Never suggest cards outside the commander's color identity.**
- **Never suggest cards that violate `profile/power-level-notes.md`** (no infinite combos,
  no land destruction as strategy, no stax — per the pilot's hard limits).
- **Flag budget impact** — if a card exceeds the pilot's per-card budget cap from
  `profile/layout.yaml`, offer a budget alternative.
- **Never auto-write** to `deck_selection.yaml` — every change is user-approved first.
