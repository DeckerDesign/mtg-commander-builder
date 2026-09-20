# 0003 — The top-to-bottom flow is a four-skill pipeline

## Status
Accepted

## Context
"Open it with a Claude agent and go" needs the whole journey — from unknown pilot to
finished exported deck — to be guided, not tribal knowledge in a README.

## Decision
Ship the pipeline as four skills in `.claude/skills/`:
1. **`intake`** — collect commanders + context; fetch Scryfall + EDHREC; vet profile items.
2. **`commander-grill`** — power-level notes (defended tier per commander) + playstyle note.
3. **`build-library`** — iterative suggest-then-vet card packages against real target commanders.
4. **`brew`** — production cycle: one intent → review gate → export.

Plus **`tune`**, a maintenance skill that adjusts commander overlays and package configs
from playtesting feedback — distinct from `brew`'s inline card-level fixes.

## Consequences
- A new pilot's path is `intake → commander-grill → build-library → brew`, each guided.
- One consistent mechanism — **suggest, then vet per item** — runs through all phases.
- Hard to reverse once pilots fork and rely on the skill names; hence recorded here.
