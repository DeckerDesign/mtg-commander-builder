# 0002 — Engine / Profile split: personal data (including card library) is config, not code

## Status
Accepted

## Context
Earlier versions hardcoded specific commander names and card lists in the Python engine.
A blank-slate template can't ship code that names one pilot's commanders.

## Decision
Split the system:
- **Engine** (`engine/`) — person-agnostic code. Hardcodes nothing about any individual.
- **Profile** (`profile/`) — all personal content AND construction config (layout targets,
  export formats, budget). The Engine reads profile data; it never contains it.

Packages, commander overlays, and cardpool are **not** an up-front form. The agent
**proposes them through the intake/build-library pipeline and confirms** before writing.

## Consequences
- The Engine is reusable as-is; personalizing the tool means editing YAML, never Python.
- "The card packages for this commander" becomes data the agent reads, not tribal knowledge.
- Adding a new commander is a single YAML file addition, no code change.
