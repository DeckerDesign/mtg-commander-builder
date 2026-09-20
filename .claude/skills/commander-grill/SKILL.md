---
name: commander-grill
description: Build the two Profile artifacts that cannot be fetched from APIs — the power-level notes (what the pilot honestly plays at and can afford, graded per commander) and the playstyle note (how they like to play, mined from their answers). A one-question-at-a-time session. Use after `intake`, or when the user says "grill me", "build my power level notes", "capture my playstyle", "what am I honestly playing at".
---

# commander-grill — power-level notes + playstyle

Phase 2 of the pipeline. `intake` gave you the *facts*; this builds the two things that make
outputs trustworthy and sound like the pilot. Run it as a grilling session: **one question at
a time, wait for the answer, never batch.**

## Part A — Power-level notes (the linchpin)

`profile/power-level-notes.md` is **authoritative**: no deck export may ever claim a higher
power level than is defensible here. It is the difference between a tool that helps someone
misrepresent their deck at the table and one that makes them credible.

Go **commander by commander** through the pilot's overlays. For each commander:

1. Ask what power level they honestly play: "Your Aesi list has Rhystic Study, Oracle of
   Mul Daya, and Cyclonic Rift. If someone at your table asked 'what power level is this?'
   what's the honest answer? Does it have a two-card combo win?"
2. **You probe; they defend.** Grade into a tier:
   - **CEDH** — fast, optimized, tutors, two-card combos, counterspell-heavy.
   - **Optimized** — strong synergies, efficient, wins by turn 5-7, some tutors.
   - **Focused** — coherent strategy, plays fair, wins turn 7-10.
   - **Casual** — fun themes, slower, no tutors, occasionally incoherent.
   - **Jank** — intentionally suboptimal, theme over function.
3. **Budget tier** — honestly: under $100 / $100-$300 / $300-$600 / $600+ per deck.
4. **What they won't play** — stax pieces? infinite combos? land destruction? Record it.
   These are hard limits on what the agent may suggest.

Hunt specifically for the dangerous overclaims: decks listed as "7" that are really optimized
8s (because the pilot doesn't want to get hated off the table), and decks listed as "8" that
are really focused 6s (because the pilot wants to seem stronger). Also capture the
**ramp-up story** (how the pilot learned their current commander) — useful for the playstyle
note and for understanding their trajectory. Write all of this to `profile/power-level-notes.md`.

## Part B — Playstyle note (preference only)

Mine `profile/playstyle.md` from the pilot's **full answers** in this session — read how they
actually talk about playing: archetypes they love, win conditions they enjoy, what frustrates
them at the table, their preferred game length, their meta (competitive FNM? casual kitchen
table?), whether they tune for the table or for consistency. Then **distill** it into a short,
persistent note so later cold sessions load it cheaply instead of re-asking everything.

Two hard boundaries:
- **Preference only, never power level.** Playstyle governs which cards *feel right*; power-
  level notes own what is objectively strong.
- Layer over the shipped **anti-generic-deck baseline** (`docs/ANTI-SLOP.md`): everyone
  avoids random good-stuff piles. The playstyle personalizes which *kind* of focused deck
  gets built.

Propose the playstyle note; the user confirms and corrects.

## Handoff

When both artifacts are written and confirmed, point the user to **`build-library`** to seed
their card packages against 3-4 target commanders.
