---
name: intake
description: Ingest a pilot's commanders, playstyle, budget, meta, and owned cards into the Profile. Fetches live data from Scryfall and EDHREC, then proposes extracted content as discrete items the user vets one by one. Use FIRST when setting up a new pilot, or when the user says "intake", "onboard me", "load my commanders", "set up my profile", "I want to build a deck".
---

# intake — ingest raw material into the Profile

Phase 1 of the pipeline (`intake → commander-grill → build-library → brew`). It turns a
pilot's commanders, cardpool, and meta context into **vetted** Profile content. It never
invents and never finalizes anything the user hasn't ratified.

## The core rule

**Extraction produces proposals, not facts.** Fetch real data, then present *candidate*
Profile items; nothing is written to `profile/` until the user accepts it.

## Step 1 — Collect commanders and context

Ask the user for:

> "Tell me which commanders you want to build or are already running. For each one I'll
> pull the Scryfall card data and EDHREC recommendations. Also: what's your rough budget
> per deck, your table's typical power level (1-10), your preferred export platform
> (Moxfield, Archidekt, MTGO, text), and do you have a list of cards you already own
> (paste a decklist or describe your collection)?"

Accept any of the following as commander or card list input:
- A commander name: "Aesi, Tyrant of Gyre Strait"
- A decklist pasted inline (one card per line, `1 Card Name` format)
- A **Scryfall search URL** (`https://scryfall.com/search?q=...`) — run it through
  `python engine/fetch_scryfall.py --url "<url>"` and treat results as candidate cards
  for the library.
- A Moxfield, Archidekt, or TappedOut URL — ask the user to export as text first,
  then paste the text list.

Loop until the user stops adding commanders.

## Step 2 — Fetch live data

For each commander the user names:

1. Call `python engine/fetch_scryfall.py "<name>"` to confirm the card exists, get its
   exact name, color identity, and current legality in Commander.
2. Call `python engine/fetch_edhrec.py "<name>"` to pull the top recommended cards,
   archetype themes, and synergy scores for that commander.
3. Read `profile/packages/*.yaml` to see what package slots already exist.

If Scryfall can't find a card, ask the user to clarify the name before proceeding.

## Step 3 — Propose, the user vets per item

Present extracted content as **discrete items**, each a separate proposal the user can
**accept / edit / reject**:

- **Identity** — pilot name, preferred platform, meta power level, playgroup size.
- **Commander overlays** — one per commander: archetype, top EDHREC synergy cards (top 20
  by synergy score), recommended packages, default power level, win condition strategy.
  Present synergy cards individually; the user keeps, swaps, or drops each.
- **Starter package cards** — for the identified color identities, propose a ramp package,
  draw package, and removal package from EDHREC + Scryfall data. 8-12 cards per package.
- **Cardpool** — if the user pasted a decklist, parse it into `profile/cardpool.yaml`
  owned list. Prompt them to flag proxies separately.

Never upgrade a claim: if EDHREC rates a card 30% inclusion, don't propose it as a "staple."
Where the source is ambiguous (a card appears in multiple archetypes), ask.

## Step 4 — Write the vetted Profile

Write only accepted items to:
- `profile/identity.yaml`
- `profile/commanders/<slug>.yaml` (one file per commander, slug = lowercase hyphenated name)
- `profile/packages/*.yaml` (update with accepted cards)
- `profile/cardpool.yaml`
- `profile/layout.yaml` (set budget_hard_cap and preferred formats)

Follow the shapes in the example files already there.

## Handoff

When the factual Profile is in place, tell the user the next step is **`commander-grill`**,
which builds the two things that can't be fetched: the **power-level notes** (what they
honestly play at and can afford) and the **playstyle note** (how they like to play). Do
not attempt those here.
