---
name: build-library
description: Seed the card package library — ramp, draw, removal, wincons, synergies, commander overlays — by iteratively suggesting candidate cards the user vets, until the library is rich enough to brew from. Uses Scryfall search and EDHREC data. Use after `commander-grill`, or when the user says "build my library", "seed my packages", "enrich the library", "add more cards".
---

# build-library — seed the card package library

Phase 3. With a vetted Profile, power-level notes, and playstyle in place, build the reusable
content `brew` will select from. Build against **real target commanders**, not in a vacuum.

## Step 1 — Collect 3-4 target commanders

Ask for 3-4 commanders the pilot wants to build (or is already running). These set the
**target color identities and archetypes** that focus your suggestions.

## Step 2 — Fetch EDHREC + Scryfall data for each

For each commander:
- `python engine/fetch_edhrec.py "<commander-name>"` → top cards by synergy score + salt score
- `python engine/fetch_scryfall.py --search "f:commander ci:<colors> t:instant o:draw" ` → supplementary searches
  for specific package slots

Use these as the *source of candidates*, not the final answer. The pilot vets every card.

## Step 3 — The iterative suggest-vet loop

Repeatedly **suggest unvetted candidate cards**, and have the user **vet each**
(accept / edit / reject). Keep going until **the user judges the library rich enough to brew
from** — no fixed count; they call it. Suggest across all package types:

- **Ramp** (`profile/packages/ramp.yaml`) — 2-3 CMC rocks, land fetchers, mana dorks for
  the relevant color identities.
- **Draw** (`profile/packages/draw.yaml`) — cantrips, engines, card advantage spells.
- **Removal** (`profile/packages/removal.yaml`) — targeted removal, board wipes, bounce.
- **Protection** (`profile/packages/protection.yaml`) — counterspells, hexproof, indestructible effects.
- **Wincons** (`profile/packages/wincons.yaml`) — finishers, combo pieces, game-ending threats.
- **Commander synergies** — in `profile/commanders/<slug>.yaml` → `synergy_cards` list.

Between rounds, name the gaps you still see: "you have no answer to artifacts/enchantments
in your green packages, and no protection for Aesi — want me to propose those?"

## Hard guardrails (same as `brew`)

- **Nothing invented.** Every suggested card must be real (verified via Scryfall), legal in
  Commander, and within the color identity of at least one of the pilot's commanders.
- **Survive power-level notes.** If the pilot's notes say "no infinite combos", never suggest
  a combo piece, even an efficient one.
- **Survive budget notes.** If the pilot has a hard cap, flag cards that exceed it rather than
  auto-including.
- **Playstyle alignment.** Style every suggestion per `profile/playstyle.md` — don't suggest
  stax pieces to a pilot who explicitly hates them.

## Validate as you go

After adding a package card, confirm it resolves cleanly:
`python engine/checks.py --validate-card "<Card Name>" --colors UG`

## Handoff

Once the library is rich enough, the pilot is ready for **`brew`** on any intent. The library
keeps growing the same way — `brew` proposes new synergy cards or package slots on demand, gated.
