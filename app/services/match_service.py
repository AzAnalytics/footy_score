# app/services/match_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Sequence

from app.core.models import Match, Quarter, PlayerStat, calc_points
from app.core.repos.matches_repo import insert_match

def validate_quarters(quarters: Sequence[Quarter]) -> list[str]:
    errs = []
    for q in quarters:
        hp = calc_points(q.home_goals, q.home_behinds)
        ap = calc_points(q.away_goals, q.away_behinds)
        if hp != q.home_points:
            errs.append(f"Q{q.q}: incohérence points domicile ({hp} ≠ {q.home_points})")
        if ap != q.away_points:
            errs.append(f"Q{q.q}: incohérence points extérieur ({ap} ≠ {q.away_points})")
    return errs

def validate_team_points(match: Match) -> list[str]:
    errs = []
    team_points = sum(ps.points for ps in match.player_stats)
    declared = match.total_home_points if match.home_club.lower() == "toulouse" else match.total_away_points
    if team_points != declared:
        errs.append(f"Somme points joueurs {team_points} ≠ points déclarés Toulouse {declared}")
    return errs

def save_post_match(match: Match) -> tuple[bool, list[str], int | None]:
    errs = []
    errs += validate_quarters(match.quarters)
    errs += validate_team_points(match)
    if errs:
        return False, errs, None
    new_id = insert_match(match)
    return True, [], new_id
