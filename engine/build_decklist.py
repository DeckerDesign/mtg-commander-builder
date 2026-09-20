#!/usr/bin/env python3
"""Export a resolved deck model to one or more decklist formats.

Supported formats:
  text       — plain "1 Card Name" per line (universally importable)
  moxfield   — same as text; Moxfield bulk-import accepts the standard format
  archidekt  — same as text; Archidekt bulk-import accepts the standard format
  mtgo       — same as text; MTGO deck import format
  tappedout  — same as text with section comments

The commander is listed separately with a `// Commander` comment for platforms
that parse it (Moxfield, Archidekt). Basic lands are grouped.

Usage:
    python engine/build_decklist.py decks/<dir>
    python engine/build_decklist.py decks/<dir> --formats moxfield text
"""
import argparse
import pathlib
from collections import Counter

import library as L

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest",
               "Wastes", "Snow-Covered Plains", "Snow-Covered Island",
               "Snow-Covered Swamp", "Snow-Covered Mountain", "Snow-Covered Forest"}


def _group_basics(lands):
    basic_counts = Counter(l for l in lands if l in BASIC_LANDS)
    nonbasic = [l for l in lands if l not in BASIC_LANDS]
    return basic_counts, nonbasic


def render_text(model, style="moxfield"):
    """Return a list of lines in the standard deckbuilding text format."""
    lines = []

    # Commander section
    lines.append("// Commander")
    lines.append(f"1 {model['commander']}")
    lines.append("")

    # Main deck by package
    by_pkg = {}
    for c in model["cards"]:
        by_pkg.setdefault(c.get("package", "other"), []).append(c["name"])

    pkg_order = ["ramp", "draw", "removal", "protection", "wincons", "synergy",
                 "utility", "required", "other"]
    seen_pkgs = set()
    for pkg in pkg_order:
        if pkg in by_pkg:
            seen_pkgs.add(pkg)
            lines.append(f"// {pkg.title()}")
            for name in sorted(by_pkg[pkg]):
                lines.append(f"1 {name}")
            lines.append("")
    for pkg, cards in sorted(by_pkg.items()):
        if pkg not in seen_pkgs:
            lines.append(f"// {pkg.title()}")
            for name in sorted(cards):
                lines.append(f"1 {name}")
            lines.append("")

    # Lands
    basic_counts, nonbasic = _group_basics(model["lands"])
    lines.append("// Lands")
    for name in sorted(nonbasic):
        lines.append(f"1 {name}")
    for name, count in sorted(basic_counts.items()):
        lines.append(f"{count} {name}")

    return lines


def export(model, deck_dir, formats=None):
    """Write all requested format files into deck_dir/output/."""
    formats = formats or ["moxfield", "text"]
    deck_dir = pathlib.Path(deck_dir)
    out_dir = deck_dir / "output"
    out_dir.mkdir(exist_ok=True)
    stub = L.output_stub(L.load_selection(deck_dir))
    written = []

    lines = render_text(model)

    for fmt in formats:
        ext_map = {
            "moxfield": ".mox",
            "archidekt": ".txt",
            "mtgo": ".dek",
            "tappedout": ".txt",
            "text": ".txt",
        }
        ext = ext_map.get(fmt, ".txt")
        suffix = f"_{fmt}" if fmt not in ("text", "moxfield") else ""
        path = out_dir / f"{stub}{suffix}{ext}"
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)

    return written


def build_from_deck(deck_dir, formats=None):
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    model = L.resolve_deck(selection)
    return export(model, deck_dir, formats=formats)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Export a deck to text formats.")
    ap.add_argument("deck_dir")
    ap.add_argument("--formats", nargs="+",
                    default=["moxfield", "text"],
                    choices=["moxfield", "archidekt", "mtgo", "tappedout", "text"],
                    help="Export formats (default: moxfield text)")
    args = ap.parse_args()
    paths = build_from_deck(args.deck_dir, formats=args.formats)
    for p in paths:
        print(f"Exported: {p}")
