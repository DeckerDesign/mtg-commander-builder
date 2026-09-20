#!/usr/bin/env python3
"""Build one deck end to end from its deck_selection.yaml.

Flow: validate the selection -> check hard rules -> export to all configured formats.
A failing hard check blocks export so an illegal deck never becomes a submission artifact.

Usage:
    python engine/apply.py decks/<dir>
    python engine/apply.py decks/<dir> --formats moxfield text archidekt
    python engine/apply.py decks/<dir> --no-color-check   # skip Scryfall color check (offline)
"""
import argparse
import pathlib
import sys

import library as L
import checks
import build_decklist


def run(deck_dir, formats=None, no_color_check=False):
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    layout = L.load_layout()
    formats = formats or layout.get("export_formats", ["moxfield", "text"])

    # 1. Validate selection resolves
    fails = checks.validate(selection)
    if fails:
        _report("selection does not resolve", fails)
        return 2

    # 2. Resolve model
    model = L.resolve_deck(selection)

    # 3. Hard checks
    hard_fails = []
    hard_fails += checks.check_count(model)
    hard_fails += checks.check_singleton(model)

    if not no_color_check:
        hard_fails += checks.check_banned(model)
        hard_fails += checks.check_color_identity(model)

    if hard_fails:
        _report("hard rule check failed (export blocked)", hard_fails)
        return 2

    # 4. Soft checks (warnings only)
    _, warnings = checks.check_deck(deck_dir)
    for w in warnings:
        print(f"  [warn] {w}")

    # 5. Export
    paths = build_decklist.export(model, deck_dir, formats=formats)
    print("Exported: " + ", ".join(str(p.name) for p in paths))

    print(f"\n[apply] DONE: {deck_dir.name} "
          f"({model['commander']}) -> archetype={model['archetype']} "
          f"power_level={model['power_level']}/10")
    return 0


def _report(headline, items):
    print(f"!! {headline}:", file=sys.stderr)
    for item in items:
        print(f"   - {item}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build and export one deck end to end.")
    ap.add_argument("deck_dir")
    ap.add_argument("--formats", nargs="+",
                    choices=["moxfield", "archidekt", "mtgo", "tappedout", "text"])
    ap.add_argument("--no-color-check", action="store_true",
                    help="Skip Scryfall color identity check (use when offline)")
    args = ap.parse_args()
    sys.exit(run(args.deck_dir, formats=args.formats, no_color_check=args.no_color_check))
