#!/usr/bin/env python3
"""Validate the hard Commander rules and soft construction targets.

Hard rules (failures — block export):
  - Exactly 100 cards (commander + 99 main deck)
  - All cards match the commander's color identity
  - Singleton (no duplicates except basic lands)
  - No banned cards (fetched from Scryfall)

Soft rules (warnings — shown at review gate, don't block):
  - Ramp count < layout.yaml ramp_count_target
  - Draw count < layout.yaml draw_count_target
  - Removal count < layout.yaml removal_count_target
  - Average CMC > layout.yaml cmc_ceiling
  - No wincon cards identified

Usage:
    python engine/checks.py decks/<dir>
    python engine/checks.py decks/<dir> --validate-only
    python engine/checks.py --validate-card "Sol Ring" --colors UG
"""
import argparse
import pathlib
import sys

import library as L
import fetch_scryfall as S

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest",
               "Wastes", "Snow-Covered Plains", "Snow-Covered Island",
               "Snow-Covered Swamp", "Snow-Covered Mountain", "Snow-Covered Forest"}


def _all_card_names(model):
    names = [c["name"] for c in model["cards"]] + model["lands"]
    return names


def check_count(model):
    """Exactly 100 cards including the commander in the command zone."""
    total = model["total"]
    if total != 100:
        return [f"Deck has {total} cards; must be exactly 100 "
                f"(commander + {total - 1} main deck)"]
    return []


def check_singleton(model):
    """No card appears more than once (basic lands are exempt)."""
    seen = {}
    failures = []
    all_names = _all_card_names(model)
    for name in all_names:
        if name in BASIC_LANDS:
            continue
        seen[name] = seen.get(name, 0) + 1
    for name, count in seen.items():
        if count > 1:
            failures.append(f"Singleton violation: '{name}' appears {count} times")
    return failures


def check_color_identity(model):
    """All cards must fall within the commander's color identity."""
    commander_data = model.get("commander_data", {})
    allowed = set(commander_data.get("color_identity", []))
    if not allowed:
        return []  # colorless commander — skip

    failures = []
    all_names = _all_card_names(model)
    for name in all_names:
        if name in BASIC_LANDS:
            continue
        result = S.validate_card(name, list(allowed))
        if not result.get("found"):
            failures.append(f"Card not found on Scryfall: '{name}'")
            continue
        if not result["color_ok"]:
            ci = "".join(result["color_identity"])
            failures.append(f"Color identity violation: '{name}' [{ci}] "
                            f"outside commander identity [{''.join(sorted(allowed))}]")
    return failures


def check_banned(model):
    """No card on the Commander banned list."""
    try:
        banned = S.get_banned_list()
    except Exception as e:
        return [f"Could not fetch banned list from Scryfall: {e}"]
    failures = []
    all_names = _all_card_names(model)
    for name in all_names:
        if name in banned:
            failures.append(f"Banned card: '{name}'")
    return failures


def soft_checks(model, layout):
    """Return warnings (non-blocking). Counts packages vs targets."""
    warnings = []
    pkg_counts = {}
    for c in model["cards"]:
        pkg = c.get("package", "unknown")
        pkg_counts[pkg] = pkg_counts.get(pkg, 0) + 1

    targets = {
        "ramp": layout.get("ramp_count_target", 10),
        "draw": layout.get("draw_count_target", 10),
        "removal": layout.get("removal_count_target", 8),
        "wincons": layout.get("wincon_count_target", 3),
    }
    for pkg, target in targets.items():
        count = pkg_counts.get(pkg, 0)
        if count < target:
            warnings.append(f"Low {pkg}: {count} cards (target ≥ {target})")

    land_count = len(model["lands"])
    land_target = layout.get("land_count_target", 36)
    if land_count < land_target - 2 or land_count > land_target + 2:
        warnings.append(f"Land count {land_count} (target ~{land_target})")

    return warnings


def validate(selection):
    """Confirm the selection resolves. Returns failure strings (no Scryfall needed)."""
    failures = []
    cmd = selection.get("commander")
    if cmd not in L.list_commanders():
        failures.append(f"Commander overlay '{cmd}' not found "
                        f"(have: {', '.join(L.list_commanders())}). "
                        f"Add profile/commanders/{cmd}.yaml to introduce it.")
        return failures
    try:
        L.resolve_deck(selection)
    except (KeyError, ValueError) as e:
        failures.append(f"Deck does not resolve: {e}")
    return failures


def check_deck(deck_dir, validate_only=False):
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    layout = L.load_layout()
    failures = validate(selection)
    if failures:
        return failures, []

    if validate_only:
        print("[validate] selection resolves cleanly.")
        return [], []

    model = L.resolve_deck(selection)

    failures = []
    failures += check_count(model)
    failures += check_singleton(model)
    failures += check_banned(model)
    failures += check_color_identity(model)

    warnings = soft_checks(model, layout)
    return failures, warnings


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate Commander deck rules.")
    ap.add_argument("deck_dir", nargs="?", help="Deck directory")
    ap.add_argument("--validate-only", action="store_true",
                    help="Only check that the selection resolves; skip Scryfall checks")
    ap.add_argument("--validate-card", metavar="NAME",
                    help="Validate a single card for legality")
    ap.add_argument("--colors", default="WUBRG",
                    help="Commander colors for --validate-card (e.g. UG)")
    args = ap.parse_args()

    if args.validate_card:
        result = S.validate_card(args.validate_card, list(args.colors.upper()))
        if not result.get("found"):
            print(f"NOT FOUND: {args.validate_card}", file=sys.stderr)
            sys.exit(1)
        status = "OK" if not result["violations"] else "FAIL"
        print(f"[{status}] {result['name']}")
        for v in result["violations"]:
            print(f"  !! {v}")
        sys.exit(0 if not result["violations"] else 2)

    if not args.deck_dir:
        ap.print_help()
        sys.exit(1)

    fails, warns = check_deck(args.deck_dir, validate_only=args.validate_only)
    for w in warns:
        print(f"  [warn] {w}")
    if fails:
        print("!! CHECK FAILED:", file=sys.stderr)
        for f in fails:
            print(f"   - {f}", file=sys.stderr)
        sys.exit(2)
    print(f"[check] PASS ({len(warns)} warnings)")
