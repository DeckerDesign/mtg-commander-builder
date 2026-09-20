#!/usr/bin/env python3
"""Monte Carlo Commander playtest simulation.

Models the user's deck across N shuffled games against a configurable pod. Uses
package-based heuristics — not a full rules engine — to track mana development,
commander cast timing, threat deployment, interaction availability, and win-condition
accessibility. Surfaces repeating failure patterns and maps each to a concrete suggestion.

Key simplification: cards are abstracted by their PACKAGE tag, not their individual
rules text. This makes the simulation fast and statistically meaningful without
requiring a full MTG engine.

Usage:
    python engine/playtest.py decks/<dir> --games 10 --auto-pod
    python engine/playtest.py decks/<dir> --games 10 --opponents "Yuriko" "Muldrotha" "Edgar Markov"
    python engine/playtest.py decks/<dir> --games 5 --pod-file opponents.json
    python engine/playtest.py decks/<dir> --games 10 --auto-pod --power 7
"""
import argparse
import json
import math
import pathlib
import random
import sys
from collections import defaultdict

import library as L
import fetch_opponents as FO

# ──────────────────────────────────────────────────────────────
# Simulation constants
# ──────────────────────────────────────────────────────────────

MAX_TURNS = 15
HAND_SIZE = 7
MULLIGAN_LAND_MIN = 2          # mulligan if opening hand has fewer lands than this
MULLIGAN_HAND_SIZE = 6         # mulligan to this size

# Package → function mapping for simulation
PKG_IS_LAND = {"lands"}
PKG_IS_RAMP = {"ramp"}
PKG_IS_DRAW = {"draw"}
PKG_IS_REMOVAL = {"removal"}
PKG_IS_PROTECTION = {"protection"}
PKG_IS_WINCON = {"wincons"}
PKG_IS_SYNERGY = {"synergy"}

# Heuristic CMC per package (used for "can I cast this?" checks)
PKG_AVG_CMC = {
    "ramp": 2.5,
    "draw": 2.8,
    "removal": 2.5,
    "protection": 2.2,
    "wincons": 6.0,
    "synergy": 3.5,
    "utility": 2.8,
    "required": 1.0,
    "lands": 0,
}

COMMANDER_CMC = 6   # read from commander overlay if available


# ──────────────────────────────────────────────────────────────
# Card pool — the 99-card main deck as a drawable list
# ──────────────────────────────────────────────────────────────

class CardPool:
    """Represents the 99-card main deck as a shuffleable list of (name, package) tuples."""

    def __init__(self, model):
        entries = []
        for c in model["cards"]:
            entries.append((c["name"], c.get("package", "other")))
        for land in model["lands"]:
            entries.append((land, "lands"))
        self._cards = entries
        self._commander_cmc = _get_commander_cmc(model)

    def shuffle(self):
        deck = list(self._cards)
        random.shuffle(deck)
        return deck

    @property
    def commander_cmc(self):
        return self._commander_cmc

    @property
    def ramp_count(self):
        return sum(1 for _, pkg in self._cards if pkg in PKG_IS_RAMP)

    @property
    def draw_count(self):
        return sum(1 for _, pkg in self._cards if pkg in PKG_IS_DRAW)

    @property
    def removal_count(self):
        return sum(1 for _, pkg in self._cards if pkg in PKG_IS_REMOVAL | PKG_IS_PROTECTION)

    @property
    def wincon_count(self):
        return sum(1 for _, pkg in self._cards if pkg in PKG_IS_WINCON)

    @property
    def land_count(self):
        return sum(1 for _, pkg in self._cards if pkg in PKG_IS_LAND)

    @property
    def total(self):
        return len(self._cards)


def _get_commander_cmc(model):
    """Read the commander's CMC from the overlay, defaulting to 6."""
    data = model.get("commander_data") or {}
    return int(data.get("cmc") or COMMANDER_CMC)


# ──────────────────────────────────────────────────────────────
# Single game simulation
# ──────────────────────────────────────────────────────────────

class GameResult:
    def __init__(self, game_num):
        self.game_num = game_num
        self.opening_hand_size = HAND_SIZE
        self.mulliganed = False
        # Key event turns (None = didn't happen in MAX_TURNS)
        self.commander_cast_turn = None
        self.first_ramp_turn = None
        self.first_draw_engine_turn = None
        self.first_wincon_turn = None
        self.projected_win_turn = None
        # Per-turn data
        self.stuck_turns = 0          # turns with no meaningful play
        self.interaction_windows = [] # [(turn, had_answer)] — each time an opp threatened
        self.cards_drawn = []         # all cards drawn this game
        self.events = []              # narrative event log
        # Opponent outcomes
        self.opponent_win_turns = {}  # {opp_name: turn}
        self.game_outcome = "unknown" # "won", "lost_to_opp", "stalemate"
        self.losing_opponent = None

    def log(self, turn, msg):
        self.events.append(f"T{turn}: {msg}")


def simulate_one_game(pool, opponents, rng=None):
    if rng is None:
        rng = random.Random()

    result = GameResult(len(opponents))
    deck = pool.shuffle()
    ptr = 0

    # --- Opening hand + mulligan ---
    hand = deck[ptr:ptr + HAND_SIZE]
    ptr += HAND_SIZE
    land_in_hand = sum(1 for _, pkg in hand if pkg in PKG_IS_LAND)
    if land_in_hand < MULLIGAN_LAND_MIN:
        result.mulliganed = True
        result.opening_hand_size = MULLIGAN_HAND_SIZE
        result.log(0, f"Mulligan (only {land_in_hand} lands). Drew {MULLIGAN_HAND_SIZE}.")
        hand = deck[ptr:ptr + MULLIGAN_HAND_SIZE]
        ptr += MULLIGAN_HAND_SIZE

    # Track state
    mana_available = 0
    ramp_in_play = 0
    draw_engines_in_play = 0
    wincons_in_play = 0
    commander_in_play = False
    commander_cast_count = 0  # for commander tax tracking

    # Pre-roll all opponent win turns
    for opp in opponents:
        mu = opp["win_turn_avg"]
        sigma = opp["win_turn_std"]
        opp_win = max(1, int(rng.gauss(mu, sigma)))
        result.opponent_win_turns[opp["commander"]] = opp_win

    earliest_opp_win = min(result.opponent_win_turns.values()) if result.opponent_win_turns else MAX_TURNS + 1

    for turn in range(1, MAX_TURNS + 1):
        # Draw a card
        if ptr < len(deck):
            drawn = deck[ptr]
            ptr += 1
            hand.append(drawn)
            result.cards_drawn.append(drawn)

        # Mana base: lands in play ~ land_count_in_deck * (turns / deck_size)
        # Approximated as: turn + ramp bonus
        land_plays_this_turn = 1  # one per turn normally
        if any(pkg in PKG_IS_RAMP for _, pkg in hand[:3]):  # rough heuristic
            land_plays_this_turn += ramp_in_play * 0.5
        mana_available = int(turn + ramp_in_play * 0.8)

        # Try to play ramp from hand
        ramp_in_hand = [(n, p) for n, p in hand if p in PKG_IS_RAMP]
        if ramp_in_hand:
            affordable = [(n, p) for n, p in ramp_in_hand
                          if PKG_AVG_CMC.get(p, 3) <= mana_available]
            if affordable:
                played = affordable[0]
                hand.remove(played)
                ramp_in_play += 1
                mana_available += 1
                if result.first_ramp_turn is None:
                    result.first_ramp_turn = turn
                    result.log(turn, f"Ramp online: {played[0]}")

        # Try to play draw engine
        draw_in_hand = [(n, p) for n, p in hand if p in PKG_IS_DRAW]
        if draw_in_hand and draw_engines_in_play == 0:
            affordable = [(n, p) for n, p in draw_in_hand
                          if PKG_AVG_CMC.get(p, 3) <= mana_available]
            if affordable:
                played = affordable[0]
                hand.remove(played)
                draw_engines_in_play += 1
                if result.first_draw_engine_turn is None:
                    result.first_draw_engine_turn = turn
                    result.log(turn, f"Draw engine online: {played[0]}")
                # Draw bonus from engine
                if ptr < len(deck):
                    bonus = deck[ptr]; ptr += 1
                    hand.append(bonus)

        # Try to cast commander
        cmd_tax = commander_cast_count * 2
        cmd_cost = pool.commander_cmc + cmd_tax
        if not commander_in_play and mana_available >= cmd_cost:
            commander_in_play = True
            commander_cast_count += 1
            if result.commander_cast_turn is None:
                result.commander_cast_turn = turn
                result.log(turn, f"Commander cast (CMC {pool.commander_cmc}, mana {mana_available})")

        # Try to play win-con
        wincon_in_hand = [(n, p) for n, p in hand if p in PKG_IS_WINCON]
        if wincon_in_hand:
            affordable = [(n, p) for n, p in wincon_in_hand
                          if PKG_AVG_CMC.get(p, 6) <= mana_available]
            if affordable:
                played = affordable[0]
                hand.remove(played)
                wincons_in_play += 1
                if result.first_wincon_turn is None:
                    result.first_wincon_turn = turn
                    result.log(turn, f"Win-con available: {played[0]}")

        # Interaction windows: check each opponent's threat turn
        for opp in opponents:
            threat_turn = opp["threat_turn"]
            if turn == threat_turn or (turn == threat_turn + 1 and turn <= MAX_TURNS):
                targets_draw = opp["targets_draw_engine"]
                # Do we have interaction?
                interaction_cards = [(n, p) for n, p in hand
                                     if p in PKG_IS_REMOVAL | PKG_IS_PROTECTION]
                has_answer = bool(interaction_cards)
                result.interaction_windows.append((turn, has_answer, opp["commander"]))
                if has_answer:
                    ans = interaction_cards[0]
                    hand.remove(ans)
                    result.log(turn, f"Used {ans[0]} against {opp['commander']} threat.")
                else:
                    result.log(turn, f"!! No answer for {opp['commander']} threat at turn {threat_turn}.")
                # Check if draw engine was targeted
                if targets_draw and draw_engines_in_play > 0 and rng.random() < opp["interaction"]:
                    draw_engines_in_play = max(0, draw_engines_in_play - 1)
                    result.log(turn, f"Draw engine removed by {opp['commander']}.")

        # Stuck turn: nothing meaningful could be played
        any_play = (ramp_in_hand and mana_available >= 1) or \
                   (wincon_in_hand and mana_available >= 4) or \
                   draw_in_hand or not commander_in_play
        if not any_play and mana_available >= 1:
            result.stuck_turns += 1

        # Commander re-cast after removal?
        if not commander_in_play and commander_cast_count > 0 and mana_available >= cmd_cost + 2:
            commander_in_play = True
            commander_cast_count += 1
            result.log(turn, f"Commander re-cast (tax {cmd_tax}, mana {mana_available})")

        # Projected win check
        if wincons_in_play >= 1 and commander_in_play and result.projected_win_turn is None:
            result.projected_win_turn = turn + 2  # rough estimate: 2 turns to close
            result.log(turn, f"Deck threatening: projected win ~turn {result.projected_win_turn}")

        # Check if an opponent would have won
        for opp_name, opp_turn in result.opponent_win_turns.items():
            if turn >= opp_turn and result.game_outcome == "unknown":
                # Did we have any relevant interaction at their win attempt?
                had_protection = any(
                    had for t, had, who in result.interaction_windows
                    if who == opp_name and t >= opp_turn - 1
                )
                if not had_protection:
                    result.game_outcome = "lost_to_opp"
                    result.losing_opponent = opp_name
                    result.log(turn, f"!! {opp_name} wins uncontested at turn {opp_turn}.")
                    break

        if result.game_outcome == "lost_to_opp":
            break

        # Check if we would win
        if result.projected_win_turn and turn >= result.projected_win_turn:
            result.game_outcome = "won"
            result.log(turn, "Deck closes out the game.")
            break

    if result.game_outcome == "unknown":
        result.game_outcome = "stalemate"

    return result


# ──────────────────────────────────────────────────────────────
# Aggregate analysis
# ──────────────────────────────────────────────────────────────

class SimulationAnalysis:
    def __init__(self, results, pool, n_games):
        self.results = results
        self.pool = pool
        self.n_games = n_games
        self._compute()

    def _compute(self):
        r = self.results
        n = self.n_games

        # Commander timing
        cmd_turns = [g.commander_cast_turn for g in r if g.commander_cast_turn]
        self.avg_cmd_turn = sum(cmd_turns) / len(cmd_turns) if cmd_turns else None
        self.cmd_by_5 = sum(1 for t in cmd_turns if t <= 5) / n
        self.cmd_by_6 = sum(1 for t in cmd_turns if t <= 6) / n
        self.cmd_by_7 = sum(1 for t in cmd_turns if t <= 7) / n
        self.cmd_never = (n - len(cmd_turns)) / n

        # Ramp timing
        ramp_turns = [g.first_ramp_turn for g in r if g.first_ramp_turn]
        self.avg_ramp_turn = sum(ramp_turns) / len(ramp_turns) if ramp_turns else None

        # Draw engine timing
        draw_turns = [g.first_draw_engine_turn for g in r if g.first_draw_engine_turn]
        self.draw_by_5 = sum(1 for t in draw_turns if t <= 5) / n
        self.avg_draw_turn = sum(draw_turns) / len(draw_turns) if draw_turns else None

        # Win-con timing
        wincon_turns = [g.first_wincon_turn for g in r if g.first_wincon_turn]
        self.wincon_by_8 = sum(1 for t in wincon_turns if t <= 8) / n
        self.avg_wincon_turn = sum(wincon_turns) / len(wincon_turns) if wincon_turns else None

        # Interaction
        all_windows = [window for g in r for window in g.interaction_windows]
        answered = [w for w in all_windows if w[1]]
        self.interaction_rate = len(answered) / len(all_windows) if all_windows else 1.0

        # Stuck turns
        self.avg_stuck = sum(g.stuck_turns for g in r) / n

        # Game outcomes
        self.win_rate = sum(1 for g in r if g.game_outcome == "won") / n
        self.loss_rate = sum(1 for g in r if g.game_outcome == "lost_to_opp") / n
        self.stalemate_rate = sum(1 for g in r if g.game_outcome == "stalemate") / n

        # Mulligan rate
        self.mulligan_rate = sum(1 for g in r if g.mulliganed) / n

    def issues(self):
        """Return a list of (severity, code, description) tuples for identified issues."""
        found = []
        avg_cmd = self.avg_cmd_turn or 99

        if avg_cmd >= 7:
            found.append(("high", "slow_commander",
                f"Commander averages turn {avg_cmd:.1f} — ramp package is too light "
                f"or curve is too high. Reached by turn 7 in only {self.cmd_by_7*100:.0f}% of games."))
        elif avg_cmd >= 6:
            found.append(("medium", "slow_commander",
                f"Commander averages turn {avg_cmd:.1f}. Healthy but borderline "
                f"— consider 1-2 cheaper ramp spells."))

        if self.cmd_never >= 0.3:
            found.append(("high", "commander_stranded",
                f"Commander never reached the battlefield in {self.cmd_never*100:.0f}% of games. "
                f"Likely a mana development issue or commander tax snowballing."))

        if self.draw_by_5 < 0.5:
            found.append(("high", "slow_draw",
                f"Draw engine online by turn 5 in only {self.draw_by_5*100:.0f}% of games. "
                f"Add lower-CMC draw effects or cantrips to smooth early turns."))
        elif self.draw_by_5 < 0.7:
            found.append(("medium", "slow_draw",
                f"Draw engine online by turn 5 in {self.draw_by_5*100:.0f}% of games "
                f"(target ≥ 70%). One additional 2-CMC draw effect would help."))

        if self.interaction_rate < 0.45:
            found.append(("high", "low_interaction",
                f"Interaction available at only {self.interaction_rate*100:.0f}% of threat windows "
                f"(target ≥ 65%). The deck frequently has no answer when opponents threaten."))
        elif self.interaction_rate < 0.65:
            found.append(("medium", "low_interaction",
                f"Interaction available at {self.interaction_rate*100:.0f}% of threat windows "
                f"(target ≥ 65%). Add 1-2 removal or protection pieces."))

        if self.wincon_by_8 < 0.4:
            found.append(("high", "slow_wincons",
                f"Win condition available by turn 8 in only {self.wincon_by_8*100:.0f}% of games "
                f"(target ≥ 60%). Win conditions are too expensive or too few."))
        elif self.wincon_by_8 < 0.6:
            found.append(("medium", "slow_wincons",
                f"Win condition available by turn 8 in {self.wincon_by_8*100:.0f}% of games. "
                f"Consider adding one lower-CMC threat or win-condition enabler."))

        if self.avg_stuck >= 2.5:
            found.append(("high", "high_stuck_turns",
                f"Average {self.avg_stuck:.1f} stuck turns per game — frequent turns with no "
                f"meaningful play. Lower the mana curve or add more early drops."))
        elif self.avg_stuck >= 1.5:
            found.append(("medium", "high_stuck_turns",
                f"Average {self.avg_stuck:.1f} stuck turns per game. "
                f"1-2 extra cheap plays (1-2 CMC) would smooth this."))

        if self.mulligan_rate >= 0.4:
            found.append(("medium", "high_mulligans",
                f"Mulliganed in {self.mulligan_rate*100:.0f}% of games — opening hands frequently "
                f"land-light. Add 1-2 more land or 1-2 more cantrips."))

        if not found:
            found.append(("low", "no_issues",
                "No significant issues detected. Deck development looks healthy across simulated games."))

        found.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x[0]])
        return found

    def suggestions(self):
        """Map each issue to concrete card swap suggestions."""
        issues = self.issues()
        suggestions = []
        for severity, code, _ in issues:
            if code == "slow_commander" or code == "commander_stranded":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A 3+ CMC ramp spell with lower impact",
                    "swap_in": "Nature's Lore / Three Visits (2 CMC, fetches Forest)",
                    "reason": "Brings mana online faster; reduces gap to commander cast.",
                    "budget": "$1-3",
                })
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A 4+ CMC non-ramp spell in a light slot",
                    "swap_in": "Explore / Coiling Oracle (2 CMC ramp + card draw)",
                    "reason": "2-CMC ramp fixes the development curve; Coiling Oracle draws as a bonus.",
                    "budget": "$0.50-2",
                })
            if code == "slow_draw":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A 4+ CMC draw spell that rarely fires early",
                    "swap_in": "Brainstorm / Ponder (1 CMC cantrip)",
                    "reason": "Cantrips smooth early turns and help find ramp; count as draw package.",
                    "budget": "$1-5",
                })
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A synergy card with high CMC and low early impact",
                    "swap_in": "Mystic Remora (1 CMC) or Archmage Emeritus",
                    "reason": "Low-CMC draw engines are online before the commander; pay off all game.",
                    "budget": "$0.50-2",
                })
            if code == "low_interaction":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "The weakest synergy card in a slot with redundancy",
                    "swap_in": "Swan Song / Negate (1-2 CMC counterspell)",
                    "reason": "Instant-speed counters answer threats at any turn; 1-2 CMC fits any mana.",
                    "budget": "$0.50-3",
                })
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A redundant win-con piece if >5 win-con slots",
                    "swap_in": "Rapid Hybridization / Beast Within (1-3 CMC hard removal)",
                    "reason": "Hard removal at low cost fills interaction windows that counters miss.",
                    "budget": "$0.25-2",
                })
            if code == "slow_wincons":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A 7+ CMC win-con that rarely resolves before game ends",
                    "swap_in": "Beastmaster Ascension / Overwhelming Stampede (4-5 CMC)",
                    "reason": "Lower-CMC win conditions are accessible 2 turns earlier on average.",
                    "budget": "$1-5",
                })
            if code == "high_stuck_turns":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A 5+ CMC card with marginal synergy",
                    "swap_in": "Coiling Oracle / Elvish Visionary (2 CMC + draw)",
                    "reason": "1-2 CMC plays eliminate stuck turns and contribute to development.",
                    "budget": "$0.25-1",
                })
            if code == "high_mulligans":
                suggestions.append({
                    "addresses": code,
                    "swap_out": "A narrow synergy card (win-more)",
                    "swap_in": "1 additional land (bring land count to 37-38)",
                    "reason": "One more land reliably reduces opening-hand mulligans.",
                    "budget": "$0.10",
                })
        return suggestions


# ──────────────────────────────────────────────────────────────
# Report formatter
# ──────────────────────────────────────────────────────────────

W = 88

def _bar(value, max_val=1.0, width=20, char="█"):
    filled = int(round(width * min(value / max(max_val, 0.0001), 1)))
    return char * filled + "░" * (width - filled)


def print_report(analysis, pod, show_game_log=False):
    n = analysis.n_games
    print("=" * W)
    print(f"PLAYTEST SIMULATION — {n} games")
    print(f"Pod: {', '.join(o['commander'] for o in pod)}")
    print("=" * W)

    # Outcomes
    print(f"\n─── OUTCOMES")
    print(f"  Win rate:      {analysis.win_rate*100:>5.0f}%  {_bar(analysis.win_rate)}")
    print(f"  Loss rate:     {analysis.loss_rate*100:>5.0f}%  {_bar(analysis.loss_rate)}")
    print(f"  Stalemate:     {analysis.stalemate_rate*100:>5.0f}%  {_bar(analysis.stalemate_rate)}")
    print(f"  Mulliganed:    {analysis.mulligan_rate*100:>5.0f}%  of opening hands")

    # Development timeline
    avg_cmd = f"turn {analysis.avg_cmd_turn:.1f}" if analysis.avg_cmd_turn else "never"
    avg_draw = f"turn {analysis.avg_draw_turn:.1f}" if analysis.avg_draw_turn else "never"
    avg_wincon = f"turn {analysis.avg_wincon_turn:.1f}" if analysis.avg_wincon_turn else "never"
    print(f"\n─── DEVELOPMENT TIMELINE")
    print(f"  Commander cast:   avg {avg_cmd}")
    print(f"    by turn 5:  {analysis.cmd_by_5*100:>5.0f}%  {_bar(analysis.cmd_by_5)}")
    print(f"    by turn 6:  {analysis.cmd_by_6*100:>5.0f}%  {_bar(analysis.cmd_by_6)}")
    print(f"    by turn 7:  {analysis.cmd_by_7*100:>5.0f}%  {_bar(analysis.cmd_by_7)}")
    print(f"    never:      {analysis.cmd_never*100:>5.0f}%  of games")
    print(f"  Draw engine:      avg {avg_draw}  |  by turn 5: {analysis.draw_by_5*100:.0f}%")
    print(f"  First win-con:    avg {avg_wincon}  |  by turn 8: {analysis.wincon_by_8*100:.0f}%")
    print(f"  Avg stuck turns:  {analysis.avg_stuck:.1f} per game")
    print(f"  Interaction rate: {analysis.interaction_rate*100:.0f}% of threat windows answered")

    # Issues
    issues = analysis.issues()
    print(f"\n─── ISSUES FOUND ({len([i for i in issues if i[0] != 'low'])} flagged)")
    for severity, code, desc in issues:
        icon = {"high": "!!", "medium": "! ", "low": "  "}[severity]
        print(f"  [{icon}] [{severity.upper():<6}] {desc}")

    # Suggestions
    suggestions = analysis.suggestions()
    if suggestions:
        print(f"\n─── SUGGESTIONS ({len(suggestions)} card swaps)")
        for i, s in enumerate(suggestions, 1):
            print(f"\n  [{i}] Addresses: {s['addresses']}")
            print(f"      Swap out:  {s['swap_out']}")
            print(f"      Swap in:   {s['swap_in']}")
            print(f"      Why:       {s['reason']}")
            print(f"      Budget:    {s['budget']}")

    # Per-game breakdown
    if show_game_log:
        print(f"\n─── PER-GAME BREAKDOWN")
        for g in analysis.results:
            cmd_turn = g.commander_cast_turn or "—"
            draw_turn = g.first_draw_engine_turn or "—"
            wincon_turn = g.first_wincon_turn or "—"
            outcome = g.game_outcome.upper()
            print(f"\n  Game {g.game_num:>2} [{outcome}]  "
                  f"Cmd T{cmd_turn}  Draw T{draw_turn}  WinCon T{wincon_turn}  "
                  f"Stuck {g.stuck_turns}  Mulligan {'Y' if g.mulliganed else 'N'}")
            for event in g.events:
                print(f"    {event}")

    print(f"\n{'=' * W}")
    print("Approve suggested swaps to update deck_selection.yaml, then re-run preview.")
    print("=" * W)


# ──────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────

def run_simulation(deck_dir, n_games=10, opponents=None, auto_pod=False,
                   pod_power=None, pod_file=None, show_game_log=False, seed=None):
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    model = L.resolve_deck(selection)
    pool = CardPool(model)

    # Build pod
    if pod_file and pathlib.Path(pod_file).exists():
        opponents = json.loads(pathlib.Path(pod_file).read_text())
    elif auto_pod or not opponents:
        if pod_power is None:
            try:
                identity = L.load_profile()["identity"]
                pod_power = identity.get("meta", {}).get("typical_table_power", 7)
            except Exception:
                pod_power = 7
        opponents = FO.select_auto_pod(pod_power, exclude_commander=selection.get("commander"))
        print(f"[playtest] Auto-selected pod (power ~{pod_power}):")
        for opp in opponents:
            print(f"  {opp['commander']} [{opp['label']}]  win ~turn {opp['win_turn_avg']}")
    else:
        opponents = [FO.build_opponent_model(name) for name in opponents]

    if seed is not None:
        random.seed(seed)

    print(f"\n[playtest] Running {n_games} games vs {len(opponents)}-player pod...")
    results = []
    for i in range(1, n_games + 1):
        g = simulate_one_game(pool, opponents)
        g.game_num = i
        results.append(g)
        print(f"  Game {i:>2}: cmd T{g.commander_cast_turn or '—'}  "
              f"outcome={g.game_outcome}  stuck={g.stuck_turns}", flush=True)

    analysis = SimulationAnalysis(results, pool, n_games)
    print()
    print_report(analysis, opponents, show_game_log=show_game_log)
    return analysis


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Playtest a Commander deck via Monte Carlo simulation.")
    ap.add_argument("deck_dir", help="Deck directory (must have deck_selection.yaml)")
    ap.add_argument("--games", type=int, default=10, help="Number of games to simulate (default 10)")
    ap.add_argument("--opponents", nargs="+", metavar="COMMANDER",
                    help="Opponent commander names (e.g. 'Yuriko' 'Edgar Markov')")
    ap.add_argument("--auto-pod", action="store_true",
                    help="Auto-select opponents from EDHREC top 100 matching your power level")
    ap.add_argument("--power", type=int, default=None,
                    help="Table power level for auto-pod selection (overrides identity.yaml)")
    ap.add_argument("--pod-file", metavar="FILE",
                    help="JSON file with saved opponent models (from a previous run)")
    ap.add_argument("--game-log", action="store_true",
                    help="Show per-game event log in the report")
    ap.add_argument("--seed", type=int, default=None,
                    help="Random seed for reproducible simulation runs")
    args = ap.parse_args()

    run_simulation(
        args.deck_dir,
        n_games=args.games,
        opponents=args.opponents,
        auto_pod=args.auto_pod or not args.opponents,
        pod_power=args.power,
        pod_file=args.pod_file,
        show_game_log=args.game_log,
        seed=args.seed,
    )
