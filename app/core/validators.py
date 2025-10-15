# Règles de cohérence (points, quart-temps…)
# app/core/validators.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple
from collections import Counter

from core.scoring import points_of, sum_quarters_match

Severity = Literal["error", "warning"]

# =========================
# Configuration (ajustable)
# =========================

# Bornes "raisonnables" (pas bloquantes si vous mettez None)
MAX_GOALS_PER_QUARTER: Optional[int] = 20
MAX_BEHINDS_PER_QUARTER: Optional[int] = 25
MAX_POINTS_PER_QUARTER: Optional[int] = 6 * (MAX_GOALS_PER_QUARTER or 30) + (MAX_BEHINDS_PER_QUARTER or 30)

# Doit-on interdire formellement les dates futures ? (sinon warning)
DISALLOW_FUTURE_DATES = False

# Saison attendue = année de la date du match ?
WARN_IF_SEASON_MISMATCH_WITH_DATE = True

# Validation sur 4 quarts numérotés 1..4 (sinon warnings)
EXPECT_4_QUARTERS = True
EXPECTED_QUART_NUMBERS: Sequence[int] = (1, 2, 3, 4)

# Pas de nom d’équipe par défaut ici — l’UI doit préciser
# soit le côté ("home"/"away"), soit le team_name concerné.


# =========================
# Modèle d’issue
# =========================

@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: Severity = "error"
    field_name: Optional[str] = None
    context: Dict[str, Any] = dc_field(default_factory=dict)

    def __str__(self) -> str:
        prefix = "⚠️" if self.severity == "warning" else "❌"
        if self.field_name:
            return f"{prefix} [{self.code}] {self.field_name}: {self.message}"
        return f"{prefix} [{self.code}] {self.message}"


# =========================
# Petits utilitaires
# =========================

def _non_empty_str(s: Any) -> bool:
    return isinstance(s, str) and s.strip() != ""

def _is_non_negative_int(x: Any) -> bool:
    try:
        return int(x) >= 0
    except Exception:
        return False

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _declared_points(match: Any, *, team_side: Optional[Literal["home", "away"]] = None, team_name: Optional[str] = None) -> Optional[int]:
    """
    Renvoie le score déclaré pour un côté précis ou pour un nom d'équipe.
    - Si team_side est fourni: on l'utilise.
    - Sinon si team_name est fourni: on détecte s'il est home ou away.
    - Sinon: None (pas de comparaison possible).
    """
    if team_side in {"home", "away"}:
        attr = "total_home_points" if team_side == "home" else "total_away_points"
        return _safe_int(getattr(match, attr, None), 0)

    if _non_empty_str(team_name):
        try:
            if getattr(match, "home_club", None) == team_name:
                return _safe_int(getattr(match, "total_home_points", None), 0)
            if getattr(match, "away_club", None) == team_name:
                return _safe_int(getattr(match, "total_away_points", None), 0)
        except Exception:
            return None
    return None


# =========================
# Validations structurelles
# =========================

def validate_match_structure(match: Any) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if not _non_empty_str(getattr(match, "home_club", None)):
        issues.append(ValidationIssue("match.home_club.missing", "Le club domicile est manquant.", "error", "home_club"))
    if not _non_empty_str(getattr(match, "away_club", None)):
        issues.append(ValidationIssue("match.away_club.missing", "Le club extérieur est manquant.", "error", "away_club"))

    thp = getattr(match, "total_home_points", None)
    tap = getattr(match, "total_away_points", None)
    if thp is None:
        issues.append(ValidationIssue("match.total_home_points.missing", "Le total des points domicile est manquant.", "error", "total_home_points"))
    if tap is None:
        issues.append(ValidationIssue("match.total_away_points.missing", "Le total des points extérieur est manquant.", "error", "total_away_points"))
    if thp is not None and not _is_non_negative_int(thp):
        issues.append(ValidationIssue("match.total_home_points.invalid", "Le total des points domicile doit être un entier ≥ 0.", "error", "total_home_points"))
    if tap is not None and not _is_non_negative_int(tap):
        issues.append(ValidationIssue("match.total_away_points.invalid", "Le total des points extérieur doit être un entier ≥ 0.", "error", "total_away_points"))

    if getattr(match, "date", None) is None:
        issues.append(ValidationIssue("match.date.missing", "La date du match est obligatoire.", "error", "date"))

    # Saison : chaîne "YYYY"
    season = getattr(match, "season_id", None)
    if not _non_empty_str(season):
        issues.append(ValidationIssue("match.season_id.missing", "La saison (ex: '2025') est obligatoire.", "error", "season_id"))
    else:
        s = str(season).strip()
        if not (len(s) == 4 and s.isdigit()):
            issues.append(ValidationIssue("match.season_id.format", "Format de saison attendu: 'YYYY'.", "warning", "season_id", {"value": s}))

    # Venue optionnel — contrôle de taille si présent
    venue = getattr(match, "venue", None)
    if venue is not None and isinstance(venue, str) and len(venue) > 120:
        issues.append(ValidationIssue("match.venue.too_long", "Le nom du lieu est anormalement long (>120).", "warning", "venue", {"len": len(venue)}))

    return issues


def validate_date_and_season(match: Any) -> List[ValidationIssue]:
    """Rapproche date et saison, et éventuellement les dates futures."""
    issues: List[ValidationIssue] = []
    d = getattr(match, "date", None)
    season = getattr(match, "season_id", None)

    # Dates futures : on prévient ou on interdit
    try:
        from datetime import date as _date
        if d and isinstance(d, (_date,)):
            today = _date.today()
            if d > today:
                sev: Severity = "error" if DISALLOW_FUTURE_DATES else "warning"
                issues.append(ValidationIssue("match.date.future", f"La date ({d}) est dans le futur.", sev, "date"))
    except Exception:
        pass

    # Saison vs date (année)
    if WARN_IF_SEASON_MISMATCH_WITH_DATE and d and _non_empty_str(season):
        try:
            y = int(str(season).strip())
            dy = getattr(d, "year", None)
            if isinstance(dy, int) and dy != y:
                issues.append(ValidationIssue(
                    "match.season_id.mismatch_with_date",
                    f"Année de saison ({y}) ≠ année de la date du match ({dy}).",
                    "warning",
                    "season_id",
                    {"season": y, "date_year": dy},
                ))
        except Exception:
            pass

    return issues


# =========================
# Validations sur quarts
# =========================

def validate_quarter_values(quarters: Iterable[Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for idx, q in enumerate(quarters or [], start=1):
        # Types & ≥0
        fields = [
            ("home_goals", getattr(q, "home_goals", None)),
            ("home_behinds", getattr(q, "home_behinds", None)),
            ("home_points", getattr(q, "home_points", None)),
            ("away_goals", getattr(q, "away_goals", None)),
            ("away_behinds", getattr(q, "away_behinds", None)),
            ("away_points", getattr(q, "away_points", None)),
        ]
        for fname, val in fields:
            if not _is_non_negative_int(val):
                issues.append(ValidationIssue(
                    "quarter.field.invalid",
                    f"Q{getattr(q, 'q', idx)}: {fname} doit être un entier ≥ 0.",
                    "error",
                    fname,
                    {"value": val, "quarter": getattr(q, "q", idx)},
                ))

        # Cohérence points = 6*goals + behinds
        hg, hb, hp = _safe_int(getattr(q, "home_goals", 0)), _safe_int(getattr(q, "home_behinds", 0)), _safe_int(getattr(q, "home_points", 0))
        ag, ab, ap = _safe_int(getattr(q, "away_goals", 0)), _safe_int(getattr(q, "away_behinds", 0)), _safe_int(getattr(q, "away_points", 0))
        if hp != points_of(hg, hb):
            issues.append(ValidationIssue(
                "quarter.home_points.formula",
                f"Q{getattr(q,'q', idx)}: incohérence points domicile ({hp} ≠ 6*{hg}+{hb}).",
                "error",
                "home_points",
            ))
        if ap != points_of(ag, ab):
            issues.append(ValidationIssue(
                "quarter.away_points.formula",
                f"Q{getattr(q,'q', idx)}: incohérence points extérieur ({ap} ≠ 6*{ag}+{ab}).",
                "error",
                "away_points",
            ))

        # Bornes raisonnables (warnings)
        if MAX_GOALS_PER_QUARTER is not None and (hg > MAX_GOALS_PER_QUARTER or ag > MAX_GOALS_PER_QUARTER):
            issues.append(ValidationIssue(
                "quarter.goals.unusually_high",
                f"Q{getattr(q,'q', idx)}: nombre de goals inhabituel (home={hg}, away={ag}).",
                "warning",
            ))
        if MAX_BEHINDS_PER_QUARTER is not None and (hb > MAX_BEHINDS_PER_QUARTER or ab > MAX_BEHINDS_PER_QUARTER):
            issues.append(ValidationIssue(
                "quarter.behinds.unusually_high",
                f"Q{getattr(q,'q', idx)}: nombre de behinds inhabituel (home={hb}, away={ab}).",
                "warning",
            ))
        if MAX_POINTS_PER_QUARTER is not None and (hp > MAX_POINTS_PER_QUARTER or ap > MAX_POINTS_PER_QUARTER):
            issues.append(ValidationIssue(
                "quarter.points.unusually_high",
                f"Q{getattr(q,'q', idx)}: total de points inhabituel (home={hp}, away={ap}).",
                "warning",
            ))

    return issues


def validate_quarter_sequence(quarters: Iterable[Any]) -> List[ValidationIssue]:
    """Numérotation unique, valeurs attendues (1..4), éventuels manquants/duplicats."""
    issues: List[ValidationIssue] = []
    qs = list(quarters or [])
    if not qs:
        return issues

    numbers = [getattr(q, "q", None) for q in qs]

    # Doublons
    counts = Counter([n for n in numbers if isinstance(n, int)])
    for n, c in counts.items():
        if c > 1:
            issues.append(ValidationIssue("quarters.duplicate_number", f"Numéro de quart dupliqué: Q{n}.", "warning", "q", {"duplicate": n}))

    # Manquants / inattendus
    if EXPECT_4_QUARTERS:
        expected = set(EXPECTED_QUART_NUMBERS)
        got = set(counts.keys())
        missing = sorted(expected - got)
        unexpected = sorted(got - expected)
        if missing:
            issues.append(ValidationIssue("quarters.missing", f"Quarts manquants: {', '.join(f'Q{x}' for x in missing)}.", "warning"))
        if unexpected:
            issues.append(ValidationIssue("quarters.unexpected", f"Quarts inattendus: {', '.join(f'Q{x}' for x in unexpected)}.", "warning"))

    return issues


def validate_match_quarters_vs_totals(match: Any) -> List[ValidationIssue]:
    """Somme des quarts == totaux match (points)."""
    issues: List[ValidationIssue] = []
    qs = list(getattr(match, "quarters", []) or [])
    if not qs:
        return issues

    try:
        sums = sum_quarters_match(qs)
        hp = sums["home"][2]
        ap = sums["away"][2]
        if hp != _safe_int(getattr(match, "total_home_points", 0)):
            issues.append(ValidationIssue("match.totals.home_mismatch", f"Somme quarts domicile ({hp}) ≠ total déclaré ({getattr(match,'total_home_points', None)}).", "error", "total_home_points"))
        if ap != _safe_int(getattr(match, "total_away_points", 0)):
            issues.append(ValidationIssue("match.totals.away_mismatch", f"Somme quarts extérieur ({ap}) ≠ total déclaré ({getattr(match,'total_away_points', None)}).", "error", "total_away_points"))
    except Exception as ex:
        issues.append(ValidationIssue("match.quarters.sum_failed", f"Échec du calcul de la somme des quarts: {ex}", "error"))

    return issues


# =========================
# Validations joueurs
# =========================

def validate_player_rows(player_stats: Iterable[Any]) -> List[ValidationIssue]:
    """Contrôle des lignes joueur (types, ≥0, points=6*goals+behinds)."""
    issues: List[ValidationIssue] = []

    for i, ps in enumerate(player_stats or [], start=1):
        name = getattr(ps, "player_name", None) if hasattr(ps, "player_name") else (ps.get("player_name") if isinstance(ps, dict) else None)

        if not _non_empty_str(name):
            issues.append(ValidationIssue("player.name.missing", f"Ligne {i}: nom de joueur manquant.", "warning", "player_name"))

        goals = getattr(ps, "goals", None) if hasattr(ps, "goals") else (ps.get("goals") if isinstance(ps, dict) else None)
        behinds = getattr(ps, "behinds", None) if hasattr(ps, "behinds") else (ps.get("behinds") if isinstance(ps, dict) else None)
        points = getattr(ps, "points", None) if hasattr(ps, "points") else (ps.get("points") if isinstance(ps, dict) else None)

        for fname, val in (("goals", goals), ("behinds", behinds), ("points", points)):
            if not _is_non_negative_int(val):
                issues.append(ValidationIssue("player.field.invalid", f"Ligne {i}: {fname} doit être un entier ≥ 0.", "error", fname, {"value": val, "row": i}))

        g, b, p = _safe_int(goals, 0), _safe_int(behinds, 0), _safe_int(points, 0)
        if p != points_of(g, b):
            issues.append(ValidationIssue("player.points.formula", f"Ligne {i}: incohérence points ({p} ≠ 6*{g}+{b}).", "error", "points"))

    return issues


def validate_duplicate_players(player_stats: Iterable[Any]) -> List[ValidationIssue]:
    """Avertit en cas de doublons de noms (insensibles à la casse/espaces)."""
    issues: List[ValidationIssue] = []
    keys: List[str] = []
    for ps in (player_stats or []):
        name = getattr(ps, "player_name", None) if hasattr(ps, "player_name") else (ps.get("player_name") if isinstance(ps, dict) else None)
        key = (name or "").strip().lower()
        if key:
            keys.append(key)
    dup_names = [n for n, c in Counter(keys).items() if c > 1]
    if dup_names:
        issues.append(ValidationIssue("players.duplicates", f"Noms de joueurs en doublon: {', '.join(sorted(dup_names))}.", "warning", "player_name"))
    return issues


def validate_players_vs_declared(match: Any, *, team_side: Optional[Literal["home", "away"]] = None, team_name: Optional[str] = None) -> List[ValidationIssue]:
    """
    Compare la somme des points joueurs au score déclaré (home/away).
    Spécifiez soit team_side ('home'/'away'), soit team_name.
    """
    issues: List[ValidationIssue] = []
    pstats = list(getattr(match, "player_stats", []) or [])
    if not pstats:
        return issues

    total_players = 0
    for ps in pstats:
        total_players += _safe_int(getattr(ps, "points", None) if hasattr(ps, "points") else (ps.get("points") if isinstance(ps, dict) else 0), 0)

    declared = _declared_points(match, team_side=team_side, team_name=team_name)
    if declared is None:
        # Pas assez de contexte pour comparer : warning informatif
        issues.append(ValidationIssue(
            "players.sum_vs_declared.skipped",
            "Comparaison joueurs vs score déclaré ignorée (team_side/team_name non fourni).",
            "warning",
            "player_stats",
        ))
        return issues

    label = team_side if team_side in {"home", "away"} else (team_name or "?")
    if total_players != declared:
        issues.append(ValidationIssue(
            "players.sum_vs_declared",
            f"Somme points joueurs ({total_players}) ≠ score déclaré ({declared}) côté {label}.",
            "error",
            "player_stats",
            {"label": label, "sum_players": total_players, "declared": declared},
        ))

    return issues


# =========================
# Agrégateur principal
# =========================

def validate_match(
    match: Any,
    *,
    team_side: Optional[Literal["home", "away"]] = None,
    team_name: Optional[str] = None,
) -> Tuple[bool, List[ValidationIssue], List[ValidationIssue]]:
    """
    Valide un objet Match complet.
    Retourne: (ok, errors, warnings)
    - Fournissez team_side OU team_name pour comparer les points joueurs au score déclaré.
    """
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []

    # 1) Structure
    issues = validate_match_structure(match)
    _split_issues(issues, errors, warnings)

    # 2) Date / Saison
    issues = validate_date_and_season(match)
    _split_issues(issues, errors, warnings)

    # 3) Quarts (valeurs + séquence + somme vs totaux)
    quarters = list(getattr(match, "quarters", []) or [])
    if quarters:
        issues = validate_quarter_values(quarters)
        _split_issues(issues, errors, warnings)

        issues = validate_quarter_sequence(quarters)
        _split_issues(issues, errors, warnings)

        issues = validate_match_quarters_vs_totals(match)
        _split_issues(issues, errors, warnings)

    # 4) Joueurs
    pstats = list(getattr(match, "player_stats", []) or [])
    if pstats:
        issues = validate_player_rows(pstats)
        _split_issues(issues, errors, warnings)

        issues = validate_duplicate_players(pstats)
        _split_issues(issues, errors, warnings)

        issues = validate_players_vs_declared(match, team_side=team_side, team_name=team_name)
        _split_issues(issues, errors, warnings)

    ok = len(errors) == 0
    return ok, errors, warnings


def _split_issues(issues: Iterable[ValidationIssue], errors_out: List[ValidationIssue], warnings_out: List[ValidationIssue]) -> None:
    for it in issues or []:
        if it.severity == "warning":
            warnings_out.append(it)
        else:
            errors_out.append(it)


# =========================
# Helpers d’affichage (optionnels)
# =========================

def issues_as_strings(issues: Iterable[ValidationIssue]) -> List[str]:
    return [str(i) for i in issues or []]


def summarize_result(ok: bool, errors: List[ValidationIssue], warnings: List[ValidationIssue]) -> str:
    if ok and not warnings:
        return "✅ Données valides."
    if ok and warnings:
        return f"✅ Données valides avec {len(warnings)} avertissement(s)."
    return f"⛔ {len(errors)} erreur(s), {len(warnings)} avertissement(s)."
