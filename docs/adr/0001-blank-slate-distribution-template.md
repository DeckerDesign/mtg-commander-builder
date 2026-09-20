# 0001 — Blank-slate distribution template

## Status
Accepted

## Context
This repo began as a specific pilot's working deck-building tool. To make it reusable,
a stranger must be able to clone it and see zero of the original pilot's data.

## Decision
The reusable template ships with a **fictional example pilot** (Alex Chen) and a real
example commander (Aesi, Tyrant of Gyre Strait) so it runs on clone. A new user forks
and fills with their own profile through the `intake` skill. **One repo per pilot** —
the Engine never has to ask "whose cardpool?" There is only one.

## Consequences
- No personal data in history.
- Template always has a complete, working reference profile and a runnable example deck.
- Multi-pilot mode rejected: complexity with no payoff for a personal tool.
