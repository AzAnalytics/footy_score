# 6*buts + behinds, agrégations
# app/core/scoring.py
from __future__ import annotations
from typing import Iterable, List, Literal, Optional, Tuple, Dict, Any
from dataclasses import dataclass

# ---------------- Base rules (AFL) ----------------

def points_of(goals: int, behinds: int) -> int:
    """Règle AFL: 1 goal = 6 pts, 1 behind = 1 pt."""
    g = int(goals or 0)
    b = int(behinds or 0)
    return g * 6 + b

def format_scoreline(goals: int, behinds: int, points: Optional[int] = None) -> str:
    """Format court: 'G.B (P)' ex: 3.2 (20). Les points sont recalculés si absents."""
    p = int(points) if points is not None else points_of(goals, behinds)
    return f"{int(goals)}.{int(behinds)} ({p})"

# ---------------- Agrégations sur quarts ----------------

@dataclass(frozen=True)
class TeamQuarter:
    goals: int
    behinds: int
    points: int

def sum_quarters_team(qs: Iterable[TeamQuarter]) -> Tuple[int, int, int]:
    """Somme (goals, behinds, points) d'une liste de quarts pour une équipe."""
    g = sum(int(q.goals or 0) for q in qs)
    b = sum(int(q.behinds or 0) for q in qs)
    p = sum(int(q.points or 0) for q in qs)
    return g, b, p

def sum_quarters_match(quarters: Iterable[Any]) -> Dict[str, Tuple[int, int, int]]:
    """
    Retourne les totaux par équipe:
    {'home': (goals, behinds, points), 'away': (...)}.
    Accepte tout objet avec attributs: home_goals/home_behinds/home_points, away_*.
    """
    home_q = [TeamQuarter(int(q.home_goals or 0), int(q.home_behinds or 0), int(q.home_points or 0)) for q in quarters]
    away_q = [TeamQuarter(int(q.away_goals or 0), int(q.away_behinds or 0), int(q.away_points or 0)) for q in quarters]
    return {"home": sum_quarters_team(home_q), "away": sum_quarters_team(away_q)}

# ---------------- Validation cohérence ----------------

def _nonneg(*vals: int) -> bool:
    return all(int(v) >= 0 for v in vals)

def validate_quarter(q: Any, idx: int) -> List[str]:
    """
    Valide 1 quart:
    - points == 6*goals + behinds (home & away)
    - valeurs non négatives
    """
    errs: List[str] = []

    hg, hb, hp = int(q.home_goals or 0), int(q.home_behinds or 0), int(q.home_points or 0)
    ag, ab, ap = int(q.away_goals or 0), int(q.away_behinds or 0), int(q.away_points or 0)
    label = f"Q{getattr(q, 'q', None) or idx}"

    if not _nonneg(hg, hb, hp, ag, ab, ap):
        errs.append(f"{label}: valeurs négatives détectées.")

    if hp != points_of(hg, hb):
        errs.append(f"{label}: incohérence points domicile ({hp} ≠ 6*{hg}+{hb}).")
    if ap != points_of(ag, ab):
        errs.append(f"{label}: incohérence points extérieur ({ap} ≠ 6*{ag}+{ab}).")
    return errs

def validate_match_consistency(match: Any) -> List[str]:
    """
    Règles:
    - Si quarts présents: chaque quart cohérent + somme quarts == totaux match.
    - Valide non-négativité des totaux match.
    - Pas de règle joueur ici (voir validate_players_vs_declared).
    """
    errs: List[str] = []

    thp = int(getattr(match, "total_home_points", 0) or 0)
    tap = int(getattr(match, "total_away_points", 0) or 0)
    if not _nonneg(thp, tap):
        errs.append("Totaux match négatifs détectés.")

    qs = list(getattr(match, "quarters", []) or [])
    if qs:
        for i, q in enumerate(qs, start=1):
            errs.extend(validate_quarter(q, i))

        sums = sum_quarters_match(qs)
        _, _, hp = sums["home"]
        _, _, ap = sums["away"]
        if hp != thp:
            errs.append(f"Somme quarts domicile ({hp}) ≠ total_home_points ({thp}).")
        if ap != tap:
            errs.append(f"Somme quarts extérieur ({ap}) ≠ total_away_points ({tap}).")
    return errs

def validate_players_vs_declared(match: Any, team_side: Literal["home", "away"]) -> List[str]:
    """
    Compare la somme des points joueurs au score déclaré du côté indiqué ('home' ou 'away').
    Évite toute dépendance à un nom de club (ex-'Toulouse').
    """
    errs: List[str] = []
    rows = list(getattr(match, "player_stats", []) or [])

    # On ne somme que les lignes "présentes" (nom non vide ou id)
    team_points = 0
    for s in rows:
        if (getattr(s, "player_name", None) or "").strip() or getattr(s, "player_id", None) is not None:
            team_points += int(getattr(s, "points", 0) or 0)

    declared = int(getattr(match, "total_home_points" if team_side == "home" else "total_away_points", 0) or 0)
    if team_points != declared:
        errs.append(f"Écart: somme points joueurs {team_points} ≠ score déclaré {declared} côté {team_side}.")
    return errs

# ---------------- Calculs "résultat" ----------------

Result = Literal["home", "away", "draw"]

def winner(match: Any) -> Result:
    thp = int(getattr(match, "total_home_points", 0) or 0)
    tap = int(getattr(match, "total_away_points", 0) or 0)
    if thp > tap:
        return "home"
    if thp < tap:
        return "away"
    return "draw"

def margin(match: Any) -> int:
    thp = int(getattr(match, "total_home_points", 0) or 0)
    tap = int(getattr(match, "total_away_points", 0) or 0)
    return abs(thp - tap)

# ---------------- Mises à jour ----------------

def compute_totals_from_quarters(match: Any) -> None:
    """
    Recalcule in-place match.total_home_points et total_away_points
    depuis les quarts. Ne touche pas aux goals/behinds cumulés du match
    (qui ne sont pas toujours stockés).
    """
    qs = list(getattr(match, "quarters", []) or [])
    if not qs:
        return
    sums = sum_quarters_match(qs)
    match.total_home_points = sums["home"][2]
    match.total_away_points = sums["away"][2]

# ---------------- Aides d’affichage ----------------

def scoreline_home_away(match: Any) -> Tuple[str, str]:
    """
    Affiche 'goals.behinds (points)' si on dispose des G/B cumulés;
    sinon '(points)' côté home/away.
    """
    thp = int(getattr(match, "total_home_points", 0) or 0)
    tap = int(getattr(match, "total_away_points", 0) or 0)

    hg = getattr(match, "total_home_goals", None)
    hb = getattr(match, "total_home_behinds", None)
    ag = getattr(match, "total_away_goals", None)
    ab = getattr(match, "total_away_behinds", None)

    if all(v is not None for v in (hg, hb, ag, ab)):
        return (
            format_scoreline(int(hg or 0), int(hb or 0), thp),
            format_scoreline(int(ag or 0), int(ab or 0), tap),
        )
    return (f"({thp})", f"({tap})")
