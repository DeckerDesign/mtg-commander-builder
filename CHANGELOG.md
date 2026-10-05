# Changelog

All notable changes to mtg-commander-builder are documented here.

---

## [Unreleased]

### Added
- **Card image galleries** — `/build-library`, `/scan-set`, and `/slot-upgrade` skills now
  publish an HTML artifact showing Scryfall card images whenever presenting suggestions.
  Up to 9 cards per gallery in a 3-column grid. `/slot-upgrade` shows cut vs. replacement
  side-by-side. Images pulled from `image_uris.normal` in the Scryfall card object — no
  extra API calls required.

- **Multi-set scope in `/build-library`** — new Step 2 asks which sets to draw from before
  any searching begins. Options: all Commander-legal cards, a specific list of set codes
  (e.g. `MH3, BLB, DSK`), or everything released after a given date. Builds a `SET_FILTER`
  that gets appended to every Scryfall query in the session.

- **macOS 26 Tahoe pip fix** — documented the two-file patch for the pip `truststore` /
  `packaging` crash (`ValueError: invalid literal for int() with base 10: ''`) that affects
  Python 3.14 on macOS Tahoe. Patch commands added to Prerequisites and Troubleshooting in
  README.

### Changed
- README prerequisites section expanded with macOS 26 Tahoe install path.
- README troubleshooting section cross-references the macOS 26 pip fix.

---

## [1.0.0] — 2026-09-20

### Added
- **`engine/playtest.py`** — Monte Carlo simulation engine. Runs up to 15 turns per game,
  tracks mana, ramp, draw engines, commander cast timing, win-con availability, and
  interaction windows. CLI: `--games`, `--auto-pod`, `--seed`, `--game-log`.

- **`engine/scan_set.py`** — New set scanner. Fetches every Commander-legal card from a set
  in the deck's color identity, scores each for archetype fit (EDHREC rank + keyword match +
  CMC), and surfaces the top cards not already in the deck, grouped by package slot.

- **`engine/slot_upgrade.py`** — Slot weakness scorer and replacement finder. Scores each
  card's replaceability by CMC vs package ideal, EDHREC rank, and archetype keyword overlap.
  Searches Scryfall for better alternatives via package-specific queries.

- **`engine/fetch_scryfall.py`** — Scryfall URL intake (`--url` flag). Accepts a full
  `scryfall.com/search?q=...` URL or raw query string. Auto-retry on HTTP 429 (waits 65s,
  retries up to 3 times).

- **`.claude/skills/scan-set/SKILL.md`** — Skill for scanning a new set release.
- **`.claude/skills/slot-upgrade/SKILL.md`** — Skill for finding weak slots and upgrades.
- **`.claude/skills/intake/SKILL.md`** — Updated to accept Scryfall URLs as direct input.

- **Zero external HTTP dependencies** — `fetch_scryfall.py` and `fetch_edhrec.py` rewritten
  from `requests` to stdlib `urllib`. `requirements.txt` now requires only `pyyaml>=6.0`.

- Full GitHub-ready README with project structure, skill reference, engine CLI reference,
  hard rules table, and troubleshooting section.

### Fixed
- Slot upgrade wincon/utility queries now exclude lands (`-t:land`) — previously EDHREC-popular
  utility lands (Urza's Saga, Evolving Wilds) dominated wincon upgrade results.
