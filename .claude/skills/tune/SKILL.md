---
name: tune
description: Adjust commander overlays and package configs from playtesting feedback — curve, package counts, power level targets, missing roles — so future brews of that commander land better. Fixes the CONFIG, not one deck's content. Use when the user says a built deck underperforms ("too slow", "no answer to X", "curve too high", "not enough interaction"), or says "tune this", "fix the overlay", "adjust the packages".
---

# tune — adjust config from playtesting feedback

The maintenance skill. When a built deck underperforms and the fix is a **configuration
change** (swap a package slot, add a new role, adjust power level target) rather than a
one-off card swap, this updates `profile/commanders/<slug>.yaml` and `profile/packages/*.yaml`
so the correction sticks for **every future brew** of that commander.

Distinct from `brew`'s inline fixes: `brew` adjusts *individual cards* to satisfy the hard
rules. `tune` changes the *package defaults and overlay* themselves when the config is wrong
for how the commander actually plays.

## When to use which

- "swap Rampant Growth for Three Visits in this deck" → that's `brew`'s card-level fix, not this.
- "every time I brew Aesi the **ramp package is too light**" / "I **always need more removal**
  for this archetype" / "the **power level target is wrong** for my meta" / "I'm always missing
  a **graveyard hate** slot" → this.

## Step 1 — Measure the complaint

Run preview on the affected deck to see current stats:
```
python engine/preview.py decks/<dir>
```

Read the playability rating breakdown. Map the complaint to a specific dimension:
"too slow" → mana curve health; "no answer to X" → interaction density; "flood of synergy
but no win" → wincon package count.

## Step 2 — Map feedback to a concrete config change

Edit `profile/commanders/<slug>.yaml` or `profile/packages/<name>.yaml`:

| Feedback | Change |
|---|---|
| "always too slow early game" | Add low-CMC ramp cards to `ramp.yaml`; lower `layout.yaml` `ramp_cmc_cap` |
| "never enough removal" | Increase `removal_count_target` in `layout.yaml`; add removal cards to `removal.yaml` |
| "missing a graveyard answer" | Add a `hate` package or extend `removal.yaml` with graveyard hate section |
| "power level target wrong" | Update `default_power_level` in commander overlay + power-level notes |
| "curve too high for my meta" | Add lower-CMC alternatives to packages; update `cmc_ceiling` |
| "win condition too narrow" | Add an alternative win-con to `wincons.yaml` under this commander |

Change the smallest thing that addresses the complaint.

## Step 3 — Re-brew and verify

Re-run brew against the same intent with the updated config:
```
python engine/preview.py decks/<dir>
```

Confirm the playability rating moved in the right direction. Iterate until it lands.
Show the user what changed in the overlay/package files and confirm before finishing.

## Scope

Commander overlays and package files are Profile config, so a tune here applies to **all
future brews** using those packages or that commander. It does **not** retroactively update
already-sleeved decks — those are your physical record. To apply the tuned config to an old
deck, run `brew` again and export a fresh list.
