# app/services/match_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, Optional, Tuple, List, Dict, Any, Literal

from core.models import Match, Quarter, PlayerStat
from core.repos.matches_repo import insert_match
from core.validators import validate_match, issues_as_strings
from core.scoring import compute_totals_from_quarters


# -----------------------------
# Petits helpers de normalisation
# -----------------------------

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _safe_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None

def _ensure_quarter(q: Any, idx: int) -> Quarter:
    """Accepte un Quarter ORM ou un dict compatible, renvoie un Quarter ORM."""
    if isinstance(q, Quarter):
        # force coercition safe (évite valeurs négatives/None bizarres)
        q.q = _safe_int(getattr(q, "q", idx), idx)
        q.home_goals = _safe_int(getattr(q, "home_goals", 0), 0)
        q.home_behinds = _safe_int(getattr(q, "home_behinds", 0), 0)
        q.home_points = _safe_int(getattr(q, "home_points", 0), 0)
        q.away_goals = _safe_int(getattr(q, "away_goals", 0), 0)
        q.away_behinds = _safe_int(getattr(q, "away_behinds", 0), 0)
        q.away_points = _safe_int(getattr(q, "away_points", 0), 0)
        return q
    # dict-like
    return Quarter(
        q=_safe_int(q.get("q", idx), idx),
        home_goals=_safe_int(q.get("home_goals", 0), 0),
        home_behinds=_safe_int(q.get("home_behinds", 0), 0),
        home_points=_safe_int(q.get("home_points", 0), 0),
        away_goals=_safe_int(q.get("away_goals", 0), 0),
        away_behinds=_safe_int(q.get("away_behinds", 0), 0),
        away_points=_safe_int(q.get("away_points", 0), 0),
    )

def _ensure_playerstat(r: Any) -> PlayerStat:
    """Accepte un PlayerStat ORM ou un dict compatible, renvoie un PlayerStat ORM."""
    if isinstance(r, PlayerStat):
        r.player_name = _safe_str(getattr(r, "player_name", None)) or "Inconnu"
        r.goals = _safe_int(getattr(r, "goals", 0), 0)
        r.behinds = _safe_int(getattr(r, "behinds", 0), 0)
        r.points = _safe_int(getattr(r, "points", 0), 0)
        # on laisse player_id tel quel (peut être None)
        return r
    return PlayerStat(
        player_id=r.get("player_id", None),
        player_name=_safe_str(r.get("player_name")) or "Inconnu",
        goals=_safe_int(r.get("goals", 0), 0),
        behinds=_safe_int(r.get("behinds", 0), 0),
        points=_safe_int(r.get("points", 0), 0),
    )

def _normalize_match(m: Match) -> Match:
    """Nettoie et normalise les champs simples du match (in-place)."""
    m.season_id = _safe_str(getattr(m, "season_id", None)) or ""
    m.venue = _safe_str(getattr(m, "venue", None))
    m.home_club = _safe_str(getattr(m, "home_club", None)) or ""
    m.away_club = _safe_str(getattr(m, "away_club", None)) or ""
    m.total_home_points = _safe_int(getattr(m, "total_home_points", 0), 0)
    m.total_away_points = _safe_int(getattr(m, "total_away_points", 0), 0)
    # quarters & player_stats
    qs: List[Any] = list(getattr(m, "quarters", []) or [])
    ps: List[Any] = list(getattr(m, "player_stats", []) or [])
    m.quarters = [_ensure_quarter(q, i + 1) for i, q in enumerate(qs)]
    m.player_stats = [_ensure_playerstat(r) for r in ps]
    return m


# -----------------------------
# Autorisation simple
# -----------------------------

def _ensure_authorized_to_create(user_ctx: Optional[Dict[str, Any]], match: Match) -> Tuple[bool, str | None]:
    """
    Règle simple: un admin peut créer n'importe quel match; sinon,
    l'équipe de l'utilisateur doit figurer en home/away.
    """
    if not user_ctx:
        # si pas de contexte, on laisse passer (à adapter si tu veux forcer)
        return True, None
    if user_ctx.get("is_admin"):
        return True, None
    team = (user_ctx.get("team_name") or "").strip()
    if not team:
        return False, "Aucune équipe associée à votre compte."
    if team not in {match.home_club, match.away_club}:
        return False, f"Non autorisé: votre équipe '{team}' ne figure pas dans ce match."
    return True, None


# -----------------------------
# Service principal
# -----------------------------

def save_post_match(
    match: Match | Dict[str, Any],
    *,
    user_ctx: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> Tuple[bool, List[str], Optional[int]]:
    """
    Valide et enregistre un match post-saisie.
    Retourne (ok, errors, new_id).

    - Normalise toutes les valeurs (int/str).
    - Recalcule les totaux à partir des quarts si présents.
    - Valide via core.validators.validate_match (quarts, totaux, joueurs).
    - Vérifie une règle d'autorisation simple (voir _ensure_authorized_to_create).
    """
    # 1) Construire/normaliser un objet Match ORM
    m: Match
    if isinstance(match, Match):
        m = match
    else:
        # dict -> Match
        m = Match(
            season_id=_safe_str(match.get("season_id")) or "",
            date=match.get("date"),  # laissé tel quel (date)
            venue=_safe_str(match.get("venue")),
            home_club=_safe_str(match.get("home_club")) or "",
            away_club=_safe_str(match.get("away_club")) or "",
            total_home_points=_safe_int(match.get("total_home_points", 0), 0),
            total_away_points=_safe_int(match.get("total_away_points", 0), 0),
        )
        m.quarters = [ _ensure_quarter(q, i+1) for i, q in enumerate(match.get("quarters", []) or []) ]
        m.player_stats = [ _ensure_playerstat(r) for r in (match.get("player_stats", []) or []) ]

    _normalize_match(m)

    # 2) Si quarts fournis, on recalcule les totaux pour éviter tout écart.
    if m.quarters:
        compute_totals_from_quarters(m)

    # 3) Déterminer le côté de l'utilisateur (pour comparer points joueurs vs score déclaré)
    team_side: Optional[Literal["home", "away"]] = None
    if user_ctx and user_ctx.get("team_name"):
        if m.home_club == user_ctx["team_name"]:
            team_side = "home"
        elif m.away_club == user_ctx["team_name"]:
            team_side = "away"

    # 4) Validation serveur
    ok_val, errors, warnings = validate_match(m, team_side=team_side)
    if not ok_val:
        # retourne toutes les erreurs (warnings ignorés)
        return False, issues_as_strings(errors), None

    # 5) Autorisation de création
    allowed, why = _ensure_authorized_to_create(user_ctx, m)
    if not allowed:
        return False, [why or "Non autorisé."], None

    # (Optionnel) notes: si tu ajoutes un champ notes côté modèle, set-le ici.
    # getattr(m, "notes", None)  # placeholder — pas de champ dans le modèle actuel.

    # 6) Persistance
    try:
        new_id = insert_match(m)
        return True, [], new_id
    except Exception as ex:
        return False, [f"Erreur enregistrement: {ex}"], None
