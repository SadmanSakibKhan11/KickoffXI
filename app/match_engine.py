"""
Match Engine Module
====================
Server-side match simulation logic for the Match Simulator feature.
Framework-agnostic — no Flask-specific imports. Takes plain Python
data in and returns plain Python data out.

Exposes:
    generate_ai_squad()      — Build the AI's starting XI + bench
    calculate_team_strength() — Average overall + random modifier
    generate_scoreline()     — Weighted random scoreline from strength gap
    select_goalscorers()     — Weighted random goalscorer assignment
    generate_substitutions() — Random subs (0–5, minutes 60–85)
    generate_match_stats()   — Possession / shots / shots on target
    select_motm()            — Man of the Match selection
    generate_match_analysis() — 1–3 sentence templated narrative
    simulate_match()         — Orchestrator: full match simulation
"""

import random
import math
import logging

logger = logging.getLogger(__name__)

from app.formations import is_player_compatible

# ── Position Category Mapping ──────────────────────────────────
POSITION_CATEGORIES = {
    'GK': 'GK',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'LWB': 'DEF', 'RWB': 'DEF',
    'CDM': 'MID', 'CM': 'MID', 'CAM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'LW': 'ATT', 'RW': 'ATT', 'ST': 'ATT', 'CF': 'ATT',
}

# Goalscorer weights by category
SCORER_WEIGHTS = {
    'ATT': 5,
    'MID': 3,
    'DEF': 1,
    'GK': 0,
}

# Difficulty settings
DIFFICULTY_CONFIG = {
    'easy':   {'pool_pct': 0.50, 'modifier_range': 4},
    'normal': {'pool_pct': 0.35, 'modifier_range': 2},
    'hard':   {'pool_pct': 0.20, 'modifier_range': 1},
}

# ── Rating Tier Thresholds (for color coding) ─────────────────
# Each tuple: (minimum_rating, tier_name, color_key)
# Ordered descending — first match wins.
RATING_TIERS = [
    (9.0, 'outstanding', 'gold'),
    (8.0, 'excellent', 'green'),
    (7.0, 'good', 'blue'),
    (6.0, 'average', 'gray'),
    (0.0, 'below_average', 'red'),
]


def get_rating_color_tier(rating):
    """
    Map a numeric match rating to its display tier and color key.

    Returns:
        Tuple (tier_name, color_key) — e.g. ('excellent', 'green').
    """
    for threshold, tier_name, color_key in RATING_TIERS:
        if rating >= threshold:
            return tier_name, color_key
    return 'below_average', 'red'


# ════════════════════════════════════════════════════════════════
# PLAYER RATINGS
# ════════════════════════════════════════════════════════════════

def calculate_player_ratings(user_xi, user_bench, ai_xi, ai_bench,
                             user_scorers, ai_scorers, user_subs, ai_subs,
                             result):
    """
    Generate a realistic match rating for every player in both squads.

    Three involvement tiers are handled distinctly:
        1. Starters — full rating range with maximum variance.
        2. Substituted-on (bench players who came on) — dampened range.
        3. Unused substitutes — narrow neutral range (5.5–6.5).

    Args:
        user_xi:      List of Player objects (user starting XI).
        user_bench:   List of Player objects (user bench).
        ai_xi:        List of Player objects (AI starting XI).
        ai_bench:     List of Player objects (AI bench).
        user_scorers: List of goalscorer dicts [{'name': ..., 'minute': ...}].
        ai_scorers:   List of goalscorer dicts.
        user_subs:    List of substitution dicts [{'player_on': ..., ...}].
        ai_subs:      List of substitution dicts.
        result:       'win', 'loss', or 'draw'.

    Returns:
        Dict with 'user' and 'ai' keys, each containing
        'starting_xi' and 'bench' lists of rating dicts:
        [{'name': str, 'rating': float, 'rating_color': str}, ...]
    """
    # Count goals per player name
    user_goal_counts = {}
    for s in user_scorers:
        user_goal_counts[s['name']] = user_goal_counts.get(s['name'], 0) + 1

    ai_goal_counts = {}
    for s in ai_scorers:
        ai_goal_counts[s['name']] = ai_goal_counts.get(s['name'], 0) + 1

    # Names of bench players who came on as substitutes
    user_subbed_on = {s['player_on'] for s in user_subs}
    ai_subbed_on = {s['player_on'] for s in ai_subs}

    def _rate_starter(player, goal_counts, team_result):
        """Rate a player who started the match."""
        # Base rating from overall: maps 0–99 → ~4.5–7.5
        base = (player.overall / 99.0) * 3.0 + 4.5

        # Result modifier
        if team_result == 'win':
            base += random.uniform(0.3, 0.7)
        elif team_result == 'loss':
            base += random.uniform(-0.5, -0.2)
        else:  # draw
            base += random.uniform(-0.2, 0.2)

        # Goal bonus
        goals = goal_counts.get(player.name, 0)
        base += goals * 0.5

        # Random variance
        base += random.uniform(-0.4, 0.4)

        return round(max(4.0, min(10.0, base)), 1)

    def _rate_subbed_on(player, goal_counts, team_result):
        """Rate a bench player who was substituted on."""
        # Dampened base
        base = ((player.overall / 99.0) * 3.0 + 4.5) * 0.85 + 1.0

        # Dampened result modifier
        if team_result == 'win':
            base += random.uniform(0.15, 0.45)
        elif team_result == 'loss':
            base += random.uniform(-0.3, -0.1)
        else:
            base += random.uniform(-0.15, 0.15)

        # Goal bonus (same as starter — a sub who scores deserves it)
        goals = goal_counts.get(player.name, 0)
        base += goals * 0.5

        # Slightly tighter random variance
        base += random.uniform(-0.3, 0.3)

        return round(max(4.0, min(10.0, base)), 1)

    def _rate_unused_sub(player):
        """Rate a bench player who never came on — narrow neutral range."""
        base = 5.8 + (player.overall / 99.0) * 0.6  # 5.8–6.4 base
        base += random.uniform(-0.2, 0.2)
        return round(max(5.5, min(6.5, base)), 1)

    def _build_team_ratings(xi_players, bench_players, goal_counts,
                            subbed_on_names, team_result):
        """Build ratings for one team's full squad."""
        xi_ratings = []
        for p in xi_players:
            r = _rate_starter(p, goal_counts, team_result)
            _, color = get_rating_color_tier(r)
            xi_ratings.append({
                'name': p.name,
                'rating': r,
                'rating_color': color,
            })

        bench_ratings = []
        for p in bench_players:
            if p.name in subbed_on_names:
                r = _rate_subbed_on(p, goal_counts, team_result)
            else:
                r = _rate_unused_sub(p)
            _, color = get_rating_color_tier(r)
            bench_ratings.append({
                'name': p.name,
                'rating': r,
                'rating_color': color,
            })

        return {
            'starting_xi': xi_ratings,
            'bench': bench_ratings,
        }

    # Determine result from each team's perspective
    user_result = result  # 'win', 'loss', or 'draw'
    if result == 'win':
        ai_result = 'loss'
    elif result == 'loss':
        ai_result = 'win'
    else:
        ai_result = 'draw'

    return {
        'user': _build_team_ratings(
            user_xi, user_bench, user_goal_counts,
            user_subbed_on, user_result,
        ),
        'ai': _build_team_ratings(
            ai_xi, ai_bench, ai_goal_counts,
            ai_subbed_on, ai_result,
        ),
    }


def _get_category(position):
    """Map a position to its category. Unknown defaults to MID."""
    cat = POSITION_CATEGORIES.get(position)
    if cat is None:
        logger.warning(f"[WARNING] Unknown position '{position}' in match engine — defaulting to MID.")
        return 'MID'
    return cat


# ════════════════════════════════════════════════════════════════
# AI SQUAD GENERATION
# ════════════════════════════════════════════════════════════════

def generate_ai_squad(formation_slots, user_player_ids, all_players, difficulty):
    """
    Generate the AI opponent's Starting XI + bench using position compatibility.

    Algorithm:
        1. Remove user-selected players from the pool.
        2. Sort pool descending by overall rating.
        3. For each formation slot, select a top candidate from the difficulty pool
           whose primary or secondary position is compatible with the slot.
        4. Generate bench with 1 GK / 2 DEF / 2 MID / 2 ATT.

    Args:
        formation_slots: List of 11 slot dicts (from formations.py).
        user_player_ids: Set/list of player IDs already selected by the user.
        all_players:     List of all Player objects.
        difficulty:      'easy', 'normal', or 'hard'.

    Returns:
        Dict with 'starting_xi' and 'bench' lists of Player objects.
    """
    config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG['normal'])
    pool_pct = config['pool_pct']

    # Step 1: Remove user-selected players and sort by overall
    user_ids_set = set(user_player_ids)
    available = [p for p in all_players if p.id not in user_ids_set]
    available.sort(key=lambda p: p.overall, reverse=True)

    # Step 2: Calculate restricted pool size by difficulty
    top_n = max(11, math.ceil(len(available) * pool_pct))
    restricted_pool = available[:top_n]

    ai_starting_xi = []
    selected_ids = set()

    # Step 3: Select starting XI slot-by-slot using Position Compatibility System
    for slot in formation_slots:
        slot_pos = slot['position']

        # Look in restricted pool for compatible candidates not yet selected
        candidates = [
            p for p in restricted_pool
            if p.id not in selected_ids and is_player_compatible(p.primary_position, p.secondary_position, slot_pos)
        ]

        # Fallback to full available pool if restricted pool has no compatible candidates
        if not candidates:
            candidates = [
                p for p in available
                if p.id not in selected_ids and is_player_compatible(p.primary_position, p.secondary_position, slot_pos)
            ]

        # Emergency fallback
        if not candidates:
            candidates = [p for p in available if p.id not in selected_ids]

        if candidates:
            # Randomly select among top 5 eligible candidates for variety
            chosen = random.choice(candidates[:min(5, len(candidates))])
            ai_starting_xi.append(chosen)
            selected_ids.add(chosen.id)

    # Step 4: Select bench (1 GK / 2 DEF / 2 MID / 2 ATT)
    bench_pool = [p for p in available if p.id not in selected_ids]
    bench_needs = {'GK': 1, 'DEF': 2, 'MID': 2, 'ATT': 2}
    ai_bench = []

    for cat, needed in bench_needs.items():
        # Find bench candidates whose category matches
        cat_candidates = [
            p for p in bench_pool
            if p.id not in selected_ids and _get_category(p.primary_position) == cat
        ]

        if len(cat_candidates) < needed:
            # Fallback to any remaining player if category pool exhausted
            cat_candidates = [p for p in bench_pool if p.id not in selected_ids]

        selected = random.sample(cat_candidates, min(needed, len(cat_candidates)))
        ai_bench.extend(selected)
        for s in selected:
            selected_ids.add(s.id)

    return {
        'starting_xi': ai_starting_xi,
        'bench': ai_bench,
    }


# ════════════════════════════════════════════════════════════════
# TEAM STRENGTH
# ════════════════════════════════════════════════════════════════

def calculate_team_strength(starting_xi_players, difficulty):
    """
    Calculate team strength as the average overall + a random modifier.

    Args:
        starting_xi_players: List of 11 Player objects.
        difficulty:          'easy', 'normal', or 'hard'.

    Returns:
        Float — team strength value.
    """
    if not starting_xi_players:
        return 50.0

    config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG['normal'])
    mod_range = config['modifier_range']

    avg = sum(p.overall for p in starting_xi_players) / len(starting_xi_players)
    modifier = random.randint(-mod_range, mod_range)

    return round(avg + modifier, 1)


# ════════════════════════════════════════════════════════════════
# SCORELINE GENERATION
# ════════════════════════════════════════════════════════════════

def generate_scoreline(user_strength, ai_strength):
    """
    Generate a realistic scoreline based on the strength difference.

    Returns:
        Tuple (user_goals, ai_goals).
    """
    gap = user_strength - ai_strength

    # Determine the favored team
    if gap > 0:
        strong_is_user = True
        abs_gap = gap
    elif gap < 0:
        strong_is_user = False
        abs_gap = -gap
    else:
        strong_is_user = random.choice([True, False])
        abs_gap = 0

    # Build weighted scoreline options based on gap
    if abs_gap <= 1.5:
        # Very close — draws and 1-goal margins
        options = [
            ((0, 0), 15), ((1, 1), 20), ((2, 2), 8),
            ((1, 0), 25), ((2, 1), 20), ((0, 1), 5),
            ((3, 2), 5), ((2, 0), 2),
        ]
    elif abs_gap <= 4:
        # Small gap — 1-goal margins more likely
        options = [
            ((1, 0), 30), ((2, 1), 25), ((2, 0), 15),
            ((0, 0), 5), ((1, 1), 8), ((3, 1), 10),
            ((3, 2), 5), ((0, 1), 2),
        ]
    elif abs_gap <= 7:
        # Moderate gap — 2-goal margins
        options = [
            ((2, 0), 25), ((3, 1), 25), ((2, 1), 15),
            ((1, 0), 10), ((4, 2), 10), ((3, 0), 10),
            ((4, 1), 5),
        ]
    else:
        # Large gap — dominant scoreline
        options = [
            ((3, 0), 25), ((3, 1), 20), ((4, 1), 20),
            ((4, 0), 10), ((5, 1), 10), ((2, 0), 10),
            ((5, 2), 5),
        ]

    # Pick a scoreline
    scorelines = [s for s, _ in options]
    weights = [w for _, w in options]
    strong_goals, weak_goals = random.choices(scorelines, weights=weights, k=1)[0]

    if strong_is_user:
        return (strong_goals, weak_goals)
    else:
        return (weak_goals, strong_goals)


# ════════════════════════════════════════════════════════════════
# GOALSCORER SELECTION
# ════════════════════════════════════════════════════════════════

def select_goalscorers(goals_count, starting_xi_players):
    """
    Assign goals to starting XI players using weighted random selection.
    Attackers have highest weight, GKs have zero weight.

    Args:
        goals_count:        Number of goals to assign.
        starting_xi_players: List of Player objects.

    Returns:
        List of dicts: [{'name': str, 'minute': int}, ...]
    """
    if goals_count == 0 or not starting_xi_players:
        return []

    # Build weight list (GK weight = 0 means GK can never score)
    eligible = []
    weights = []
    for p in starting_xi_players:
        cat = _get_category(p.primary_position)
        w = SCORER_WEIGHTS.get(cat, 1)
        if w > 0:
            eligible.append(p)
            weights.append(w)

    if not eligible:
        return []

    scorers = []
    used_minutes = set()

    for _ in range(goals_count):
        player = random.choices(eligible, weights=weights, k=1)[0]

        # Generate a unique minute
        minute = random.randint(1, 90)
        attempts = 0
        while minute in used_minutes and attempts < 50:
            minute = random.randint(1, 90)
            attempts += 1
        used_minutes.add(minute)

        scorers.append({
            'name': player.name,
            'minute': minute,
        })

    # Sort by minute
    scorers.sort(key=lambda x: x['minute'])
    return scorers


# ════════════════════════════════════════════════════════════════
# SUBSTITUTIONS
# ════════════════════════════════════════════════════════════════

def generate_substitutions(starting_xi_players, bench_players):
    """
    Generate random substitutions (0–5 per team).
    Each sub occurs between minutes 60–85. Position-appropriate
    matching is attempted where possible.

    Returns:
        List of dicts: [{'player_off': str, 'player_on': str, 'minute': int}, ...]
    """
    if not bench_players or not starting_xi_players:
        return []

    num_subs = random.randint(0, min(5, len(bench_players)))
    if num_subs == 0:
        return []

    # Categorize bench
    bench_by_cat = {}
    for p in bench_players:
        cat = _get_category(p.primary_position)
        bench_by_cat.setdefault(cat, []).append(p)

    # Categorize starters (available for substitution)
    starter_by_cat = {}
    for p in starting_xi_players:
        cat = _get_category(p.primary_position)
        starter_by_cat.setdefault(cat, []).append(p)

    subs = []
    used_bench = set()
    used_starters = set()
    used_minutes = set()

    for _ in range(num_subs):
        # Find a bench player not yet used
        bench_player = None
        bench_cat = None

        # Try categories that have available bench AND starter players
        available_cats = [
            cat for cat in bench_by_cat
            if any(p.id not in used_bench for p in bench_by_cat[cat])
        ]
        if not available_cats:
            break

        bench_cat = random.choice(available_cats)
        bench_options = [p for p in bench_by_cat[bench_cat] if p.id not in used_bench]
        if not bench_options:
            continue
        bench_player = random.choice(bench_options)

        # Find a starter in a matching or adjacent category to come off
        starter_player = None

        # Try same category first
        same_cat_starters = [
            p for p in starter_by_cat.get(bench_cat, [])
            if p.id not in used_starters
        ]
        if same_cat_starters:
            starter_player = random.choice(same_cat_starters)
        else:
            # Fall back to any non-GK starter not yet subbed
            all_available = [
                p for p in starting_xi_players
                if p.id not in used_starters and _get_category(p.primary_position) != 'GK'
            ]
            if all_available:
                starter_player = random.choice(all_available)

        if not starter_player:
            continue

        # Generate unique minute between 60–85
        minute = random.randint(60, 85)
        attempts = 0
        while minute in used_minutes and attempts < 30:
            minute = random.randint(60, 85)
            attempts += 1
        used_minutes.add(minute)

        used_bench.add(bench_player.id)
        used_starters.add(starter_player.id)

        subs.append({
            'player_off': starter_player.name,
            'player_on': bench_player.name,
            'minute': minute,
        })

    subs.sort(key=lambda x: x['minute'])
    return subs


# ════════════════════════════════════════════════════════════════
# MATCH STATISTICS
# ════════════════════════════════════════════════════════════════

def generate_match_stats(user_goals, ai_goals, user_strength, ai_strength):
    """
    Generate match statistics consistent with the outcome.

    Returns:
        Dict with 'user' and 'ai' sub-dicts, each containing
        possession, shots, shots_on_target.
    """
    total_strength = user_strength + ai_strength
    if total_strength == 0:
        total_strength = 1  # Avoid division by zero

    # Possession (based on strength ratio with some randomness)
    base_poss = (user_strength / total_strength) * 100
    user_possession = max(30, min(70, round(base_poss + random.randint(-5, 5))))
    ai_possession = 100 - user_possession

    # Shots (stronger team generally takes more)
    total_shots = random.randint(18, 32)
    user_shot_ratio = user_possession / 100
    user_shots = max(3, round(total_shots * user_shot_ratio + random.randint(-3, 3)))
    ai_shots = max(3, total_shots - user_shots)

    # Ensure teams with more goals have at minimum that many shots on target
    min_user_sot = max(user_goals, 1)
    min_ai_sot = max(ai_goals, 1)

    # Shots on target (subset of shots)
    user_sot = max(min_user_sot, min(user_shots, round(user_shots * random.uniform(0.3, 0.6))))
    ai_sot = max(min_ai_sot, min(ai_shots, round(ai_shots * random.uniform(0.3, 0.6))))

    return {
        'user': {
            'possession': user_possession,
            'shots': user_shots,
            'shots_on_target': user_sot,
        },
        'ai': {
            'possession': ai_possession,
            'shots': ai_shots,
            'shots_on_target': ai_sot,
        },
    }


# ════════════════════════════════════════════════════════════════
# MAN OF THE MATCH
# ════════════════════════════════════════════════════════════════

def select_motm(user_xi, ai_xi, user_scorers, ai_scorers, user_goals, ai_goals):
    """
    Select Man of the Match from both teams' starting XI.

    Scoring: overall * 0.3 + goals * 2.0 + (team_won ? 1.5 : 0) + random(0, 1.5)

    Returns:
        Dict with name, team ('user'/'ai'), rating (float 6.0–9.5).
    """
    user_won = user_goals > ai_goals
    ai_won = ai_goals > user_goals

    # Count goals per player
    user_goal_counts = {}
    for s in user_scorers:
        user_goal_counts[s['name']] = user_goal_counts.get(s['name'], 0) + 1

    ai_goal_counts = {}
    for s in ai_scorers:
        ai_goal_counts[s['name']] = ai_goal_counts.get(s['name'], 0) + 1

    candidates = []

    for p in user_xi:
        goals = user_goal_counts.get(p.name, 0)
        score = (p.overall * 0.3) + (goals * 2.0) + (1.5 if user_won else 0) + random.uniform(0, 1.5)
        candidates.append((p, 'user', score, goals))

    for p in ai_xi:
        goals = ai_goal_counts.get(p.name, 0)
        score = (p.overall * 0.3) + (goals * 2.0) + (1.5 if ai_won else 0) + random.uniform(0, 1.5)
        candidates.append((p, 'ai', score, goals))

    if not candidates:
        return None

    # Select highest scoring candidate
    candidates.sort(key=lambda x: x[2], reverse=True)
    motm_player, motm_team, motm_score, motm_goals = candidates[0]

    # Generate a match rating (6.0–9.5 range, correlated with MOTM score)
    # Normalize score to rating range
    min_possible = 0
    max_possible = 99 * 0.3 + 5 * 2.0 + 1.5 + 1.5  # ~42.2
    normalized = (motm_score - min_possible) / (max_possible - min_possible) if max_possible > min_possible else 0.5
    rating = 6.0 + normalized * 3.5
    rating = round(min(9.5, max(6.0, rating)), 1)

    return {
        'name': motm_player.name,
        'team': motm_team,
        'rating': rating,
        'overall': motm_player.overall,
        'nationality': motm_player.nationality,
        'primary_position': motm_player.primary_position,
    }


# ════════════════════════════════════════════════════════════════
# MATCH ANALYSIS
# ════════════════════════════════════════════════════════════════

def generate_match_analysis(result, user_score, ai_score, user_strength,
                            ai_strength, motm, user_scorers, ai_scorers):
    """
    Generate a 1–3 sentence match analysis narrative.

    Args:
        result:        'win', 'loss', or 'draw'.
        user_score:    Int — user team goals.
        ai_score:      Int — AI team goals.
        user_strength: Float — user team strength.
        ai_strength:   Float — AI team strength.
        motm:          MOTM dict (name, team, rating).
        user_scorers:  List of user goalscorer dicts.
        ai_scorers:    List of AI goalscorer dicts.

    Returns:
        String — match analysis text.
    """
    strength_gap = abs(user_strength - ai_strength)
    total_goals = user_score + ai_score

    sentences = []

    # Opening sentence about the result
    if result == 'draw':
        if total_goals == 0:
            openers = [
                "A hard-fought match ended in a goalless stalemate.",
                "Both sides cancelled each other out in a tense 0-0 draw.",
                "Neither team could find the breakthrough in a closely contested affair.",
            ]
        else:
            openers = [
                f"An entertaining {user_score}-{ai_score} draw saw both teams share the spoils.",
                f"The match finished level at {user_score}-{ai_score} after an evenly-matched contest.",
                f"A dramatic encounter ended {user_score}-{ai_score} with neither side able to claim victory.",
            ]
    elif result == 'win':
        if user_score - ai_score >= 3:
            openers = [
                f"A dominant {user_score}-{ai_score} victory showcased the team's overwhelming superiority.",
                f"Your Team delivered a commanding {user_score}-{ai_score} win in a one-sided affair.",
            ]
        elif user_score - ai_score >= 2:
            openers = [
                f"A convincing {user_score}-{ai_score} victory demonstrated your squad's quality.",
                f"Your Team secured a comfortable {user_score}-{ai_score} win with a disciplined performance.",
            ]
        else:
            openers = [
                f"A narrow {user_score}-{ai_score} win was enough to secure all three points.",
                f"Your Team edged a tight contest {user_score}-{ai_score} in an intense battle.",
            ]
    else:  # loss
        if ai_score - user_score >= 3:
            openers = [
                f"A heavy {user_score}-{ai_score} defeat saw the AI's squad prove too strong.",
                f"The opposition was ruthless in a comprehensive {user_score}-{ai_score} loss.",
            ]
        elif ai_score - user_score >= 2:
            openers = [
                f"A {user_score}-{ai_score} loss reflected the quality gap between the two sides.",
                f"Despite efforts, a {user_score}-{ai_score} defeat was the final outcome.",
            ]
        else:
            openers = [
                f"A narrow {user_score}-{ai_score} defeat left your squad wondering what might have been.",
                f"The AI Select XI edged the contest {ai_score}-{user_score} in a tightly-fought match.",
            ]

    sentences.append(random.choice(openers))

    # Sentence about strength comparison
    if strength_gap > 5:
        if user_strength > ai_strength:
            sentences.append("The significant quality advantage was evident throughout the match.")
        else:
            sentences.append("The opposition's superior squad quality was the decisive factor.")
    elif strength_gap > 2:
        sentences.append("The slight edge in overall squad quality proved influential.")

    # MOTM mention
    if motm:
        motm_phrases = [
            f"{motm['name']} earned Man of the Match honors with an outstanding {motm['rating']} rating.",
            f"A standout display from {motm['name']} (rated {motm['rating']}) caught the eye of pundits.",
            f"{motm['name']} was named Man of the Match after an impressive {motm['rating']}-rated performance.",
        ]
        sentences.append(random.choice(motm_phrases))

    return ' '.join(sentences)


# ════════════════════════════════════════════════════════════════
# MAIN SIMULATION ORCHESTRATOR
# ════════════════════════════════════════════════════════════════

def simulate_match(user_starting_xi_players, user_bench_players,
                   formation_slots, difficulty, all_players):
    """
    Run a complete match simulation.

    Args:
        user_starting_xi_players: List of 11 Player objects (user's starting XI).
        user_bench_players:       List of 7 Player objects (user's bench).
        formation_slots:          List of 11 formation slot dicts.
        difficulty:               'easy', 'normal', or 'hard'.
        all_players:              List of all Player objects.

    Returns:
        Dict — complete match result (see data contract in implementation plan).
    """
    # Collect all user player IDs
    user_all_ids = [p.id for p in user_starting_xi_players] + [p.id for p in user_bench_players]

    # Generate AI squad
    ai_squad = generate_ai_squad(formation_slots, user_all_ids, all_players, difficulty)
    ai_starting_xi = ai_squad['starting_xi']
    ai_bench = ai_squad['bench']

    # Calculate team strengths
    user_strength = calculate_team_strength(user_starting_xi_players, difficulty)
    ai_strength = calculate_team_strength(ai_starting_xi, difficulty)

    # Generate scoreline
    user_goals, ai_goals = generate_scoreline(user_strength, ai_strength)

    # Determine result
    if user_goals > ai_goals:
        result = 'win'
    elif user_goals < ai_goals:
        result = 'loss'
    else:
        result = 'draw'

    # Select goalscorers
    user_scorers = select_goalscorers(user_goals, user_starting_xi_players)
    ai_scorers = select_goalscorers(ai_goals, ai_starting_xi)

    # Generate substitutions
    user_subs = generate_substitutions(user_starting_xi_players, user_bench_players)
    ai_subs = generate_substitutions(ai_starting_xi, ai_bench)

    # Generate match statistics
    stats = generate_match_stats(user_goals, ai_goals, user_strength, ai_strength)

    # Select Man of the Match
    motm = select_motm(
        user_starting_xi_players, ai_starting_xi,
        user_scorers, ai_scorers,
        user_goals, ai_goals,
    )

    # Generate match analysis
    analysis = generate_match_analysis(
        result, user_goals, ai_goals,
        user_strength, ai_strength,
        motm, user_scorers, ai_scorers,
    )

    # Calculate player ratings for all players in both squads
    ratings = calculate_player_ratings(
        user_starting_xi_players, user_bench_players,
        ai_starting_xi, ai_bench,
        user_scorers, ai_scorers,
        user_subs, ai_subs,
        result,
    )

    # Enrich MOTM with consistent rating from unified ratings data
    if motm:
        motm_team_key = motm['team']  # 'user' or 'ai'
        motm_ratings_list = ratings[motm_team_key]['starting_xi']
        motm_rating_entry = next(
            (r for r in motm_ratings_list if r['name'] == motm['name']),
            None,
        )
        if motm_rating_entry:
            # Override the MOTM rating with the unified calculated rating
            motm['rating'] = motm_rating_entry['rating']
            motm['rating_color'] = motm_rating_entry['rating_color']
        else:
            _, color = get_rating_color_tier(motm['rating'])
            motm['rating_color'] = color

        # Add goal count to MOTM
        all_scorers = user_scorers + ai_scorers
        motm['goals'] = sum(1 for s in all_scorers if s['name'] == motm['name'])

    # Build result payload
    def _serialize_players(players):
        """Serialize a list of Player objects to dicts."""
        return [p.to_dict() for p in players]

    return {
        'result': result,
        'user_team': {
            'name': 'Your Team',
            'score': user_goals,
            'strength': user_strength,
            'goalscorers': user_scorers,
            'substitutions': user_subs,
            'stats': stats['user'],
            'starting_xi': _serialize_players(user_starting_xi_players),
            'bench': _serialize_players(user_bench_players),
            'ratings': ratings['user'],
        },
        'ai_team': {
            'name': 'AI Select XI',
            'score': ai_goals,
            'strength': ai_strength,
            'goalscorers': ai_scorers,
            'substitutions': ai_subs,
            'stats': stats['ai'],
            'starting_xi': _serialize_players(ai_starting_xi),
            'bench': _serialize_players(ai_bench),
            'ratings': ratings['ai'],
        },
        'motm': motm,
        'match_analysis': analysis,
    }

