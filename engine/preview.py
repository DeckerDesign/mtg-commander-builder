#!/usr/bin/env python3
"""Render-free REVIEW GATE preview: show the real resolved deck with stats.

This is what the agent shows at the review gate (WORKFLOW step 5) — the actual
assembled deck, never a paraphrase. Shows: full card list grouped by package,
mana curve (ASCII), package breakdown, playability rating, gaps, acquisition list.

Usage:
    python engine/preview.py decks/<dir>
    python engine/preview.py decks/<dir> --no-acquire   # skip acquisition list
"""
import argparse
import pathlib

import library as L
import fetch_scryfall as S

W = 90


def _bar(value, max_value, width=20):
    filled = int(round(width * value / max(max_value, 1)))
    return "█" * filled + "░" * (width - filled)


def show(deck_dir, show_acquire=True):
    deck_dir = pathlib.Path(deck_dir)
    sel = L.load_selection(deck_dir)
    layout = L.load_layout()

    try:
        model = L.resolve_deck(sel)
    except (KeyError, ValueError) as e:
        print(f"!! Could not resolve deck: {e}")
        return

    print("=" * W)
    print(f"Commander: {model['commander']}  |  Archetype: {model['archetype']}")
    print(f"Power Level: {model['power_level']}/10  |  {model['power_level_fit']}")
    if model.get("strategy_hook"):
        print(f"Strategy: {model['strategy_hook']}")
    print("=" * W)

    # --- Package breakdown ---
    pkg_counts = {}
    for c in model["cards"]:
        pkg = c.get("package", "other")
        pkg_counts[pkg] = pkg_counts.get(pkg, 0) + 1
    pkg_counts["lands"] = len(model["lands"])

    targets = {
        "ramp": layout.get("ramp_count_target", 10),
        "draw": layout.get("draw_count_target", 10),
        "removal": layout.get("removal_count_target", 8),
        "wincons": layout.get("wincon_count_target", 3),
        "lands": layout.get("land_count_target", 36),
    }

    print("\n--- PACKAGE BREAKDOWN")
    for pkg, count in sorted(pkg_counts.items()):
        target = targets.get(pkg)
        flag = ""
        if target and count < target:
            flag = f" !! below target ({target})"
        bar = _bar(count, max(count, target or count, 1))
        print(f"  {pkg:<14} {count:>3}  {bar}{flag}")

    print(f"\n  TOTAL (incl. commander): {model['total']} cards")

    # --- Mana curve (fetch CMCs) ---
    print("\n--- MANA CURVE (nonland cards)")
    cmc_buckets = {}
    total_cmc = 0
    nonland_count = 0
    for c in model["cards"]:
        card_data = S.card_by_name(c["name"])
        if card_data:
            cmc = int(card_data.get("cmc", 0))
            if "Land" not in (card_data.get("type_line") or ""):
                bucket = min(cmc, 7)
                cmc_buckets[bucket] = cmc_buckets.get(bucket, 0) + 1
                total_cmc += cmc
                nonland_count += 1

    max_bucket = max(cmc_buckets.values(), default=1)
    labels = {0: "0 ", 1: "1 ", 2: "2 ", 3: "3 ", 4: "4 ", 5: "5 ", 6: "6 ", 7: "7+"}
    for i in range(8):
        count = cmc_buckets.get(i, 0)
        bar = _bar(count, max_bucket, 24)
        print(f"  CMC {labels[i]} {bar} {count}")

    avg_cmc = total_cmc / max(nonland_count, 1)
    cmc_ceil = layout.get("cmc_ceiling", 3.5)
    cmc_flag = " !! above target" if avg_cmc > cmc_ceil else ""
    print(f"\n  Avg CMC: {avg_cmc:.2f} (target ≤ {cmc_ceil}){cmc_flag}")

    # --- Full card list by package ---
    print("\n--- FULL CARD LIST")
    by_pkg = {}
    for c in model["cards"]:
        pkg = c.get("package", "other")
        by_pkg.setdefault(pkg, []).append(c)

    for pkg, cards in sorted(by_pkg.items()):
        print(f"\n  [{pkg.upper()}]")
        for c in cards:
            acq = " [ACQUIRE]" if c["acquire"] else ""
            proxy = " [proxy]" if c["proxy"] else ""
            print(f"    1 {c['name']}{acq}{proxy}")

    if model["lands"]:
        print(f"\n  [LANDS]")
        for land in model["lands"]:
            print(f"    1 {land}")

    # --- Gaps ---
    if model.get("gaps"):
        print("\n--- GAPS / HONEST NOTES")
        for g in model["gaps"]:
            print(f"  - {g}")

    # --- Acquisition list ---
    if show_acquire and model.get("acquire"):
        print("\n--- ACQUISITION LIST")
        total_price = 0.0
        for item in model["acquire"]:
            price = S.price_usd(item["name"])
            price_str = f"${price}" if price else "?"
            try:
                total_price += float(price or 0)
            except ValueError:
                pass
            print(f"  {item['name']:<45} {price_str:>8}  [{item.get('package','')}]")
        if total_price:
            print(f"\n  Estimated acquisition cost: ${total_price:.2f}")

    # --- Playability rating ---
    print("\n--- PLAYABILITY RATING")
    _print_rating(model, layout, avg_cmc, pkg_counts, targets)

    print("\n" + "=" * W)
    print("REVIEW GATE — approve this deck before exporting.")
    print("=" * W)


def _print_rating(model, layout, avg_cmc, pkg_counts, targets):
    """Compute and display the 0-100 playability score."""
    score = 0

    # Mana curve health (0-25)
    ramp = pkg_counts.get("ramp", 0)
    ramp_target = targets.get("ramp", 10)
    ramp_score = min(ramp / ramp_target, 1.0) * 12
    cmc_ceil = layout.get("cmc_ceiling", 3.5)
    cmc_score = max(0, 1 - max(0, avg_cmc - cmc_ceil) / 1.5) * 13
    curve_pts = int(ramp_score + cmc_score)
    score += curve_pts

    # Interaction density (0-25)
    removal = pkg_counts.get("removal", 0) + pkg_counts.get("protection", 0)
    removal_target = targets.get("removal", 8)
    interaction_pts = int(min(removal / removal_target, 1.0) * 25)
    score += interaction_pts

    # Synergy density (0-25)
    synergy = pkg_counts.get("synergy", 0)
    total_nonland = sum(v for k, v in pkg_counts.items() if k != "lands")
    synergy_ratio = synergy / max(total_nonland, 1)
    synergy_pts = int(min(synergy_ratio / 0.25, 1.0) * 25)
    score += synergy_pts

    # Win condition presence (0-25)
    wincons = pkg_counts.get("wincons", 0)
    wincon_target = targets.get("wincons", 3)
    wincon_pts = int(min(wincons / wincon_target, 1.0) * 25)
    score += wincon_pts

    power_level = max(1, min(10, int(score / 10)))
    tier = {10: "CEDH", 9: "CEDH", 8: "Optimized", 7: "Optimized",
            6: "Focused", 5: "Focused", 4: "Casual", 3: "Casual",
            2: "Jank", 1: "Jank"}.get(power_level, "Casual")

    bar = _bar(score, 100, 30)
    print(f"  Score:   {score}/100  {bar}")
    print(f"  Rating:  {power_level}/10 — {tier}")
    print(f"  Curve:   {curve_pts}/25  |  Interaction: {interaction_pts}/25  |  "
          f"Synergy: {synergy_pts}/25  |  Win-cons: {wincon_pts}/25")

    claimed = model.get("power_level", 0)
    if claimed and abs(claimed - power_level) > 1:
        direction = "higher" if claimed > power_level else "lower"
        print(f"  !! Claimed power level ({claimed}) is {direction} than the rating "
              f"suggests ({power_level}). Adjust claim or the deck.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Show resolved deck + stats (no export).")
    ap.add_argument("deck_dir")
    ap.add_argument("--no-acquire", action="store_true", help="Skip acquisition list")
    args = ap.parse_args()
    show(pathlib.Path(args.deck_dir), show_acquire=not args.no_acquire)
