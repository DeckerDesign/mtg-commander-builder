# 0004 — Power-level notes are authoritative on power; playstyle is preference only

## Status
Accepted

## Context
The system's value is credibility: decks that represent their actual power level at the
table, not efficient overclaiming. Two failure modes threaten this — claiming a higher
power level to impress, and absorbing the pilot's *aspirational claims* from their answers
(everyone thinks their deck is a 7 when it might be a 5 or a 9).

## Decision
Two separate artifacts with a strict boundary:
- **Power-level notes** (`profile/power-level-notes.md`) — authoritative on **objective
  power**. Built by probing each commander and having the pilot defend it; graded into tiers
  (CEDH / optimized / focused / casual / jank). No deck may claim beyond it.
- **Playstyle note** (`profile/playstyle.md`) — governs **preference only**: what archetypes
  feel right, what the pilot enjoys, what they won't play. Never governs objective power claims.

**Playstyle never overrides power level.** "I enjoy fast decks" does not justify claiming
a power level the deck can't defend at the table.

## Consequences
- The tool makes pilots credible at their table instead of helping them misrepresent their decks.
- Playstyle note can safely record preferences without those preferences inflating power claims.
- Every downstream skill (`build-library`, `brew`) is capped by the power-level notes.
