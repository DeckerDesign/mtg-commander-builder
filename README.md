# mtg-commander-builder

You've been staring at EDHREC for three hours. You have 40 Scryfall tabs open. Your maybe-board has 247 cards. Your mana curve "looks fine." Jace has already read the minds of every Commander player on the internet and distilled it into synergy scores — this tool reads those scores so you don't have to be a telepath about it.

Feed a commander and a play intent in, get a tuned, export-ready 100-card deck out — grounded in what you can actually pilot and afford. Claude reads your intent and chooses the cards; a deterministic **Engine** validates, enforces rules, and exports. No hallucinated cards, no invented synergies — everything is sourced from Scryfall and EDHREC, then vetted by you. The Engine is the Judge, Unworthy: it cannot be negotiated with, and it will not let you export a 97-card deck.

Clone it, open it with Claude Code, and run top to bottom: from "I want to build Aesi" to a finished, 100-card deck exported to Moxfield. Unlike Jace, it remembers what it was doing the whole time.

---

## Who this is for

**Not a coder?** You only need to know how to open a terminal and run a few commands. The hardest part is installing Python — the rest is conversational. Every step says what to type.

**A developer?** The architecture is an Engine/Profile split: person-agnostic deterministic Python against YAML profile files. Skills are `.claude/skills/<name>/SKILL.md` files that Claude loads as guided workflows. All data sources are Scryfall + EDHREC with local JSON caching. Zero external dependencies beyond PyYAML.

---

## What it does

```
intake → commander-grill → build-library → brew
```

1. **`intake`** — tell it your commanders, budget, and meta. It fetches live data from Scryfall and EDHREC, proposes your Profile content, and you approve each item.
2. **`commander-grill`** — a conversation that builds the two things it can't look up: your honest **power-level notes** (what you actually play at) and your **playstyle note** (how you like to play).
3. **`build-library`** — Claude iteratively suggests cards for each slot (ramp, draw, removal, protection, win-cons, synergies) from EDHREC + Scryfall, and you vet each one until the library is rich enough.
4. **`brew`** — give it an intent (e.g. "build Aesi landfall value, power 7"). Claude drafts a 100-card `deck_selection.yaml`, shows you a full preview with stats, and only exports once you approve.

**After your deck is built — four more tools:**

5. **`playtest`** — Monte Carlo simulation: 5-10 games against a configurable pod (import real decklists, pull from EDHREC top 100, or auto-fill). Surfaces failure patterns with concrete card swap suggestions.
6. **`scan-set`** — scan a new set release for cards that fit your deck. Give it a set code (`MH3`, `BLB`, `DSK`) or a Scryfall URL and it returns top fits by slot.
7. **`slot-upgrade`** — find the weakest cards in your deck and get concrete replacements. Auto-scans all slots or targets a specific package or card.
8. **`tune`** — adjust the deck based on playtest feedback without rebuilding from scratch.

---

## Prerequisites

### Everyone needs these

1. **Python 3.8 or newer** — [python.org/downloads](https://www.python.org/downloads/)
   - On Mac: open Terminal, type `python3 --version`. If you see `Python 3.x.x`, you're good.
   - On Windows: open Command Prompt, type `python --version`.
   - If not installed, download from the link above and run the installer.

2. **Claude Code** — the CLI that runs the skills
   - Install: `npm install -g @anthropic/claude-code`
   - Or download the desktop app at [claude.ai/download](https://claude.ai/download) (recommended for beginners — no terminal needed to install)
   - You'll need an [Anthropic account](https://console.anthropic.com) to log in.

3. **PyYAML** — the only external Python dependency
   ```bash
   pip3 install pyyaml
   ```
   On Windows: `pip install pyyaml`

4. **Git** (to clone the repo) — [git-scm.com](https://git-scm.com/downloads)
   - On Mac: already installed. Type `git --version` to check.
   - On Windows: download and run the installer from the link above.

That's it. No database, no other installs. The engine fetches Scryfall and EDHREC over the internet; those are free and require no accounts.

---

## Setup (step by step)

### 1. Clone the repo

```bash
git clone https://github.com/DeckerDesign/mtg-commander-builder.git
cd mtg-commander-builder
```

### 2. Install the one dependency

```bash
pip3 install pyyaml
```

### 3. Open it with Claude Code

```bash
claude
```

That's all. You're now in the tool. Type your first command:

```
/intake
```

Claude will ask you questions and guide you through the rest.

---

## Quick start — if you already have a decklist

If you have an existing decklist (exported from Moxfield, Archidekt, or anywhere that gives you `1 Card Name` per line), you can skip straight to import:

1. Export your deck as a text file from your deckbuilding site.
2. Run `/intake` and paste the list when Claude asks.
3. Claude fetches Scryfall + EDHREC data for your commander and proposes the full profile.
4. Run `/commander-grill` to set your power level and playstyle.
5. Run `/brew` with your intent to get the validated 100-card export.

---

## Full skill reference

All skills are invoked by typing `/skill-name` inside a Claude Code session.

### `/intake` — first-time setup
Builds your Profile from scratch. Give Claude your commander names, budget, table power level, preferred export platform (Moxfield, Archidekt, MTGO, text), and optionally an existing decklist to import.

**Accepts:**
- Commander name: `"Aesi, Tyrant of Gyre Strait"`
- Pasted decklist (one card per line, `1 Card Name` format)
- Scryfall search URL: paste `https://scryfall.com/search?q=...` directly

**Writes:** `profile/identity.yaml`, `profile/commanders/<slug>.yaml`, `profile/packages/*.yaml`, `profile/cardpool.yaml`

---

### `/commander-grill` — power level + playstyle
A one-question-at-a-time session. Claude asks targeted questions and builds:
- `profile/power-level-notes.md` — **authoritative**: what tier you play at per commander, your budget tiers, hard limits (no infinite combos, no stax, etc.)
- `profile/playstyle.md` — style-only: how you like to play (value vs combo, fast vs grindy, favorite strategies)

Nothing downstream may claim beyond what power-level-notes says.

---

### `/build-library` — grow your card package library
Claude searches Scryfall and EDHREC for candidates in each package slot (ramp, draw, removal, protection, win-cons, synergies) and presents them one by one for you to accept or reject. Run this until the library feels rich enough to brew from. You can always return and add more.

---

### `/brew` — build and export a deck
Give Claude an intent like "build Aesi landfall combo, power 7, budget $300". Claude:
1. Drafts a `deck_selection.yaml` (100-card selection from your library)
2. Runs the Engine to resolve the full deck
3. Shows you a **review gate**: commander info, card list by slot, mana curve, playability rating (0-100 across curve / interaction / synergy / win-cons), acquisition list with prices
4. **Stops and waits for your approval**
5. On approval: validates (count, singleton, color identity, banned list), then exports

**Export formats** (set in `profile/layout.yaml`):
- `.mox` — Moxfield import
- `.txt` — Archidekt / generic text
- `.dek` — MTGO format

---

### `/playtest` — simulate games against a pod
Runs 5-10 Monte Carlo games of your deck against a configurable pod. Not a full rules engine — package-based heuristics that model mana development, commander timing, threat windows, and win-con availability.

**Pod options:**
- **A) Import real decklists** — paste or drop opponent decklists and Claude models them
- **B) EDHREC top 100** — Claude fetches top commanders filtered by power level, you pick 2-3
- **C) Auto-fill** — Claude auto-selects opponents matching your typical table power

**Output:** win rate, average commander cast turn, interaction rate at threat windows, draw engine online %, stuck turns, plus concrete card swap suggestions matched to each issue.

```bash
python engine/playtest.py decks/<dir> --games 10 --auto-pod
python engine/playtest.py decks/<dir> --games 10 --opponents "Yuriko" "Muldrotha" "Edgar Markov"
python engine/playtest.py decks/<dir> --games 5 --auto-pod --game-log
```

---

### `/scan-set` — scan a new set for additions
Fetches every Commander-legal card from a set in your color identity, scores each for archetype fit, and returns the top cards you haven't already included — grouped by package slot.

```bash
python engine/scan_set.py MH3 decks/<dir> --top 10
python engine/scan_set.py DSK decks/<dir> --package draw --budget 10
```

Also accepts a Scryfall URL directly:
```bash
python engine/fetch_scryfall.py --url "https://scryfall.com/search?q=e%3Amh3+ci%3Aug"
```

---

### `/slot-upgrade` — find weak cards and suggest replacements
Scores each card in your deck by replaceability (CMC vs package ideal, EDHREC rank, archetype keyword match), then searches Scryfall for better alternatives.

```bash
python engine/slot_upgrade.py decks/<dir> --auto                    # scan all slots
python engine/slot_upgrade.py decks/<dir> --package ramp --top 5    # one slot
python engine/slot_upgrade.py decks/<dir> --card "Solemn Simulacrum" # specific card
python engine/slot_upgrade.py decks/<dir> --auto --budget 5         # budget filter
```

---

### `/tune` — adjust from feedback
After playtesting or table sessions, describe what's wrong ("too slow", "no graveyard hate", "curve too high") and Claude adjusts the commander overlay and packages without rebuilding from scratch.

---

## Running the Engine directly

You don't need to go through Claude for every operation. All engine scripts run from the command line:

```bash
# Preview your deck (no export)
python engine/preview.py decks/001_example-aesi-landfall

# Validate only (checks count, singleton, color identity, banned list)
python engine/checks.py decks/001_example-aesi-landfall --validate-only

# Full build + export
python engine/apply.py decks/001_example-aesi-landfall

# Simulate games
python engine/playtest.py decks/001_example-aesi-landfall --games 10 --auto-pod

# Scan a set
python engine/scan_set.py MH3 decks/001_example-aesi-landfall --top 10

# Find upgrades
python engine/slot_upgrade.py decks/001_example-aesi-landfall --auto

# Look up a card
python engine/fetch_scryfall.py "Aesi, Tyrant of Gyre Strait"

# Search Scryfall
python engine/fetch_scryfall.py --search "f:commander ci:UG o:landfall t:creature cmc<=4"

# Search from a Scryfall URL you copied
python engine/fetch_scryfall.py --url "https://scryfall.com/search?q=..."

# Pull EDHREC data for a commander
python engine/fetch_edhrec.py "Aesi, Tyrant of Gyre Strait" --top 30
```

---

## Project structure

```
mtg-commander-builder/
│
├── engine/                     Deterministic Python — no personal data here
│   ├── library.py              Core resolver: deck_selection.yaml → 100-card model
│   ├── checks.py               Hard rule enforcement: count, singleton, color identity, banned list
│   ├── preview.py              Print resolved deck + mana curve + playability rating
│   ├── apply.py                Orchestrator: validate → resolve → check → export
│   ├── build_decklist.py       Export: Moxfield (.mox), text (.txt), MTGO (.dek)
│   ├── fetch_scryfall.py       Scryfall API: card lookup, search, URL intake, banned list
│   ├── fetch_edhrec.py         EDHREC JSON API: top cards by synergy, archetype themes
│   ├── fetch_opponents.py      Opponent modeling for playtest: archetypes, auto-pod selection
│   ├── playtest.py             Monte Carlo simulation engine: per-game events + report
│   ├── scan_set.py             New set scanner: color-filtered + archetype-scored results
│   └── slot_upgrade.py         Slot weakness scorer + Scryfall replacement finder
│
├── profile/                    YOU — replace all of this with your own content
│   ├── identity.yaml           Pilot name, preferred platform, meta power, budget
│   ├── power-level-notes.md    AUTHORITATIVE: power tiers, budget caps, hard limits
│   ├── playstyle.md            Style/preference note (how you like to play)
│   ├── layout.yaml             Deck size, package count targets, CMC ceiling, export formats
│   ├── cardpool.yaml           Cards you own / proxy / want
│   ├── commanders/             One .yaml per commander: color identity, archetype, overlays
│   │   └── aesi-tyrant-of-gyre-strait.yaml    (example — replace or add your own)
│   └── packages/               Reusable card pool, organized by function
│       ├── ramp.yaml
│       ├── draw.yaml
│       ├── removal.yaml
│       ├── protection.yaml
│       └── wincons.yaml
│
├── decks/                      One folder per built deck — the reproducible record
│   └── 001_example-aesi-landfall/
│       ├── intent.md           What you wanted to build (freeform note)
│       └── deck_selection.yaml The agent's output: which cards from which packages
│
├── .claude/skills/             Claude workflows — invoked with /skill-name
│   ├── intake/SKILL.md
│   ├── commander-grill/SKILL.md
│   ├── build-library/SKILL.md
│   ├── brew/SKILL.md
│   ├── playtest/SKILL.md
│   ├── scan-set/SKILL.md
│   ├── slot-upgrade/SKILL.md
│   └── tune/SKILL.md
│
├── .scryfall_cache/            Auto-created local cache — never commit this
├── docs/
│   ├── ANTI-SLOP.md            What generic deck-building advice looks like — avoid it
│   └── adr/                    Architecture Decision Records (why things are the way they are)
├── CONTEXT.md                  Glossary of all terms used in the codebase
├── WORKFLOW.md                 Canonical workflow top to bottom
└── requirements.txt            One dependency: pyyaml
```

---

## Hard rules (the Engine enforces — do not break)

These are checked automatically before every export. A deck cannot be exported if any fail.

| Rule | What it checks |
|---|---|
| **Exactly 100 cards** | Commander + 99. Basic lands may appear multiple times; all others are singleton. |
| **Singleton** | No duplicate non-basic land names. |
| **Color identity** | Every card's color identity must be a subset of the commander's. |
| **Banned list** | No cards on the official Commander banned list (fetched live from Scryfall). |
| **Power-level notes** | Nothing in `deck_selection.yaml` may exceed what `power-level-notes.md` allows. |

Soft checks (warnings, not blockers): package counts vs targets in `layout.yaml`.

---

## Replacing the example Profile

The repo ships with a fictional example pilot (`profile/`) and a built example deck (`decks/001_example-aesi-landfall/`). To make it yours:

1. **Clear the example:**
   ```bash
   rm -rf decks/001_example-aesi-landfall
   rm profile/commanders/aesi-tyrant-of-gyre-strait.yaml
   ```

2. **Clear or replace profile files:** edit `profile/identity.yaml`, `profile/cardpool.yaml`, `profile/layout.yaml`, and the package files — or just run `/intake` and let Claude rebuild them.

3. **Delete the example power-level and playstyle notes:**
   ```bash
   rm profile/power-level-notes.md
   rm profile/playstyle.md
   ```
   Then run `/commander-grill` to build yours from scratch.

---

## Key design decisions

| Decision | Why |
|---|---|
| Engine/Profile split | The engine has no personal data. Swap your profile without touching code. |
| YAML deck_selection.yaml | Human-readable, version-controlled, diffable. You can edit it by hand. |
| Local JSON cache for API calls | Scryfall and EDHREC calls are cached in `.scryfall_cache/`. Offline re-runs are fast. |
| No external dependencies except PyYAML | The fetch layer uses Python's stdlib `urllib`. Nothing to install beyond PyYAML. |
| Review gate before every export | Nothing writes to your deck until you approve the resolved preview. |
| Package-based simulation (not full rules engine) | Fast, statistically meaningful. A full rules engine would need thousands of lines for edge cases that don't change the statistical story. |
| power-level-notes.md is authoritative | Claude cannot suggest cards above what you've committed to in writing. |

Full rationale in [docs/adr/](docs/adr/).

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'yaml'`**
```bash
pip3 install pyyaml
```

**`Scryfall HTTP 429: rate_limited`**
You hit Scryfall's rate limit (10 req/s max). The engine auto-retries after 65 seconds. If it keeps happening, delete `.scryfall_cache/` and re-run — cached results don't count against the limit.

**`Commander overlay 'xyz' not found`**
You referenced a commander in `deck_selection.yaml` that doesn't have a file in `profile/commanders/`. Run `/intake` for that commander to generate the overlay, or create `profile/commanders/<slug>.yaml` manually using the existing example as a template.

**`Total cards: 97 (target: 100)`**
Your `deck_selection.yaml` is short. The engine counts the commander as 1 of 100. Check `lands:` — basic lands need the count notation (`- 8 Forest`, not `- Forest` repeated 8 times).

**EDHREC fetch errors**
EDHREC's JSON API is unofficial. If it's down, the skill falls back to a hardcoded list of top commanders. Scryfall still works; you just won't get synergy scores for that session.

---

## Contributing

This is an open template — clone it, swap out the example profile, and it's yours. If you fix a bug or improve the Engine, open a PR. Keep the Engine/Profile split clean: nothing personal goes in `engine/`.

---

## Acknowledgements

Card data from [Scryfall](https://scryfall.com) (free, no auth required).  
Commander recommendations from [EDHREC](https://edhrec.com) (unofficial JSON API).  
Architecture pattern adapted from [application-tool-template](https://github.com/rwlopez98/application-tool-template).
