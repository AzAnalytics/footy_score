# 6*buts + behinds, agrégations
# app/core/scoring.py
from __future__ import annotations
from typing import Iterable, List, Literal, Optional, Tuple, Dict
from dataclasses import dataclass

# Rappels métier AFL
def points_of(goals: int, behinds: int) -> int:
    return goals * 6 + behinds

def format_scoreline(goals: int, behinds: int, points: Optional[int] = None) -> str:
    """Ex: 3.2 (20)"""
    p = points if points is not None else points_of(goals, behinds)
    return f"{goals}.{behinds} ({p})"

# -------- Agrégations sur quarts-temps --------

@dataclass
class TeamQuarter:
    goals: int
    behinds: int
    points: int

def sum_quarters_team(qs: Iterable[TeamQuarter]) -> Tuple[int, int, int]:
    g = sum(q.goals for q in qs)
    b = sum(q.behinds for q in qs)
    p = sum(q.points for q in qs)
    return g, b, p

def sum_quarters_match(quarters) -> Dict[str, Tuple[int, int, int]]:
    """Retourne (home_totals, away_totals) sous forme (goals, behinds, points)"""
    home_q = [TeamQuarter(q.home_goals, q.home_behinds, q.home_points) for q in quarters]
    away_q = [TeamQuarter(q.away_goals, q.away_behinds, q.away_points) for q in quarters]
    return {
        "home": sum_quarters_team(home_q),
        "away": sum_quarters_team(away_q),
    }

# -------- Validation cohérence --------

def validate_quarter(q, idx: int) -> List[str]:
    errs: List[str] = []
    if q.home_points != points_of(q.home_goals, q.home_behinds):
        errs.append(f"Q{q.q or idx}: incohérence points domicile ( {q.home_points} ≠ 6*{q.home_goals}+{q.home_behinds} )")
    if q.away_points != points_of(q.away_goals, q.away_behinds):
        errs.append(f"Q{q.q or idx}: incohérence points extérieur ( {q.away_points} ≠ 6*{q.away_goals}+{q.away_behinds} )")
    return errs

def validate_match_consistency(match) -> List[str]:
    """
    Règles:
    - si quarts présents: chaque quart cohérent + somme quarts == totaux match
    - pas de règle sur joueurs ici (peut être fait via validate_players_vs_declared)
    """
    errs: List[str] = []
    qs = list(getattr(match, "quarters", []) or [])
    if qs:
        # 1) chaque quart
        for i, q in enumerate(qs, start=1):
            errs.extend(validate_quarter(q, i))
        # 2) somme des quarts == totaux
        sums = sum_quarters_match(qs)
        hg, hb, hp = sums["home"]
        ag, ab, ap = sums["away"]
        if hp != match.total_home_points:
            errs.append(f"Somme quarts domicile ({hp}) ≠ total_home_points ({match.total_home_points})")
        if ap != match.total_away_points:
            errs.append(f"Somme quarts extérieur ({ap}) ≠ total_away_points ({match.total_away_points})")
    else:
        # pas de quarts : rien à valider ici (les points home/away sont saisis en final)
        pass
    return errs

def validate_players_vs_declared(match, toulouse_name: str = "Toulouse") -> List[str]:
    """
    Compare la somme des points joueurs de Toulouse au score déclaré de Toulouse (home ou away).
    """
    errs: List[str] = []
    rows = list(getattr(match, "player_stats", []) or [])
    team_points = sum((s.points or 0) for s in rows if (s.player_name or "").strip())
    declared = match.total_home_points if match.home_club == toulouse_name else match.total_away_points
    if team_points != declared:
        errs.append(
            f"Écart: somme points joueurs {team_points} ≠ score déclaré {declared} pour {toulouse_name}"
        )
    return errs

# -------- Calculs "résultat" --------

Result = Literal["home", "away", "draw"]

def winner(match) -> Result:
    if match.total_home_points > match.total_away_points:
        return "home"
    if match.total_home_points < match.total_away_points:
        return "away"
    return "draw"

def margin(match) -> int:
    return abs(match.total_home_points - match.total_away_points)

# -------- Utilitaires "mise à jour" --------

def compute_totals_from_quarters(match) -> None:
    """Recalcule match.total_home_points et total_away_points depuis les quarts (in-place)."""
    qs = list(getattr(match, "quarters", []) or [])
    if not qs:
        return
    sums = sum_quarters_match(qs)
    match.total_home_points = sums["home"][2]
    match.total_away_points = sums["away"][2]

# -------- Aides d’affichage --------

def scoreline_home_away(match) -> Tuple[str, str]:
    """
    Produit 'goals.behinds (points)' pour home et away si on dispose des totaux G/B.
    Si seuls les points totaux sont connus (pas G/B), retourne '(points)'.
    """
    # Si on n’a pas les G/B cumulés, on affiche au minimum (points)
    hg = getattr(match, "total_home_goals", None)
    hb = getattr(match, "total_home_behinds", None)
    ag = getattr(match, "total_away_goals", None)
    ab = getattr(match, "total_away_behinds", None)

    if all(v is not None for v in (hg, hb, ag, ab)):
        return (
            format_scoreline(hg, hb, match.total_home_points),
            format_scoreline(ag, ab, match.total_away_points),
        )
    return (f"({match.total_home_points})", f"({match.total_away_points})")
