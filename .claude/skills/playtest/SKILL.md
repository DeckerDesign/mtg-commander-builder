---
name: playtest
description: Run a Monte Carlo simulation of 5-10 games against a configurable pod — either user-imported decklists or commanders pulled from EDHREC's top 100 — then surface bottlenecks, issue patterns, and concrete card swap suggestions. Use when the user says "playtest this", "simulate games", "test against the pod", "how does this deck perform", "find weaknesses", "run some games".
---

# playtest — simulate games and surface issues

Runs a statistical simulation of the user's built deck against a Commander pod. Uses
package-based heuristics (not a full rules engine) to model mana development, threat
timelines, interaction windows, and win conditions across 5-10 shuffled games. Surfaces
repeating failure patterns and maps them to concrete card suggestions.

## Before anything: read the Profile

Read `profile/power-level-notes.md` (authoritative on power level target and hard limits),
`profile/playstyle.md` (governs what suggestions are acceptable), and the built deck's
`deck_selection.yaml`. Confirm the deck passes hard checks first:
`python engine/checks.py decks/<dir> --validate-only`

## Step 1 — Configure the pod

Ask the user how they want to build the pod:

> "How should I fill the pod?
> A) **Import your pod's real decks** — paste each decklist (or drop files in
>    `profile/sources/`) and I'll model them.
> B) **Pull from EDHREC top 100** — I'll fetch the current top commanders, you pick
>    2-3 from the list (filtered by your typical table power level), and I'll build
>    heuristic opponent models.
> C) **Quick auto-fill** — I'll auto-select opponents matching your typical table
>    power level from EDHREC's top commanders. Just say go."

For A: Run `python engine/fetch_opponents.py --parse <file_or_text>` for each deck.
For B: Run `python engine/fetch_opponents.py --top 100 --power <N>` to list candidates,
        then confirm 2-3 selections with the user.
For C: Run `python engine/fetch_opponents.py --auto --power <N>` with the pilot's
        `meta.typical_table_power` from `profile/identity.yaml`.

## Step 2 — Run the simulation

```
python engine/playtest.py decks/<dir> --games 10 --pod <opponent1> <opponent2> <opponent3>
```

Or with a saved pod config:
```
python engine/playtest.py decks/<dir> --games 10 --pod-file <path>
```

The simulation runs N shuffled games, tracking per-game events (commander cast turn,
first threat, first draw engine, interaction availability at key windows, win timeline)
and aggregates across all games.

Show the simulation output to the user. It is long — present the summary section first,
then offer to show the per-game breakdown on request.

## Step 3 — Review gate

Present results in this order:

1. **Headline stats** — average commander cast turn, % games hit key milestones, estimated
   win % vs pod, average first threat turn.
2. **Issues found** — flagged failure patterns (e.g. "commander too slow in 7/10 games",
   "no answer to resolved threat in 4/10 games").
3. **Suggestions** — concrete card swaps from `profile/packages/*.yaml` or external sources,
   matched to each issue. Each suggestion includes: the card to swap out, the card to swap in,
   and the specific issue it addresses.
4. **Per-game breakdown** — on request only.

**Stop and wait for the user.** The simulation is a diagnostic, not a prescription — the
user vets every suggested change. Nothing is written to `deck_selection.yaml` until approved.

## Step 4 — Apply approved changes

For each approved suggestion:
1. Edit `deck_selection.yaml` to make the swap.
2. Re-run preview: `python engine/preview.py decks/<dir>`
3. Optionally re-run the simulation to confirm improvement:
   `python engine/playtest.py decks/<dir> --games 5 --pod-file <same-config>`
4. If the playability rating improved and the user is satisfied, `python engine/apply.py`
   to export the updated deck.

## Hard limits on suggestions

- **Never suggest cards that violate `profile/power-level-notes.md`** — no infinite combos
  or power-level tiers above what the notes allow.
- **Never suggest cards outside the commander's color identity.**
- **Never suggest cards that violate the pilot's hard limits** (playstyle.md — no stax,
  no land destruction as strategy, etc.).
- **Flag budget impact** — if a suggested card exceeds the pilot's budget per card,
  offer a budget alternative alongside it.

## Reading the simulation output

| Metric | Healthy | Warning | Problem |
|---|---|---|---|
| Commander cast avg turn | ≤ 5 | 6 | ≥ 7 |
| % games with draw engine by turn 5 | ≥ 70% | 50-70% | < 50% |
| % games with win-con by turn 8 | ≥ 60% | 40-60% | < 40% |
| Interaction available at threat windows | ≥ 65% | 45-65% | < 45% |
| Bottleneck turns (stuck turns) | ≤ 1.5 avg | 1.5-2.5 | ≥ 2.5 |

A "stuck turn" is a turn where no meaningful play was available due to mana constraints
or card-draw variance. High stuck-turn counts indicate curve or ramp problems.
