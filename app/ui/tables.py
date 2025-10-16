# Tables/metrics réutilisables
# app/ui/tables.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Dict, Any, Optional
from datetime import date

import pandas as pd
import streamlit as st

from core.scoring import (
    scoreline_home_away,
    sum_quarters_match,
)

# ------------------------------
# Utils d'accès/format
# ------------------------------

def _get(obj: Any, name: str, default: Any = None) -> Any:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default

def _to_date_str(x: Any) -> Any:
    try:
        return pd.to_datetime(x).date().isoformat()
    except Exception:
        return x

def _download_row(df: pd.DataFrame, filename_prefix: str, key_prefix: str = "dl") -> None:
    """Affiche deux boutons de téléchargement (CSV/JSON) avec encodages propres."""
    if df is None or df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8")
    jsonb = df.to_json(orient="records").encode("utf-8")
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Télécharger CSV",
        data=csv,
        file_name=f"{filename_prefix}.csv",
        mime="text/csv",
        key=f"{key_prefix}-csv",
    )
    c2.download_button(
        "⬇️ Télécharger JSON",
        data=jsonb,
        file_name=f"{filename_prefix}.json",
        mime="application/json",
        key=f"{key_prefix}-json",
    )

def show_dataframe(
    df: pd.DataFrame,
    caption: Optional[str] = None,
    use_container_width: bool = True,
    key: Optional[str] = None,
) -> None:
    if caption:
        st.caption(caption)
    st.dataframe(df, use_container_width=use_container_width, hide_index=True, key=key)


# ------------------------------
# Tableaux de matches
# ------------------------------

def matches_table(
    rows: Iterable[Any],
    title: Optional[str] = None,
    show_download: bool = False,
    key_prefix: str = "matches",
) -> pd.DataFrame:
    data: List[Dict[str, Any]] = []
    for m in rows or []:
        data.append({
            "ID": _get(m, "id"),
            "Date": _to_date_str(_get(m, "date")),
            "Saison": _get(m, "season_id"),
            "Domicile": _get(m, "home_club"),
            "Extérieur": _get(m, "away_club"),
            "Pts Dom": _get(m, "total_home_points"),
            "Pts Ext": _get(m, "total_away_points"),
            "Lieu": _get(m, "venue"),
        })
    df = pd.DataFrame(data)
    # tri du plus récent si possible
    if not df.empty and "Date" in df.columns:
        try:
            df = df.sort_values("Date", ascending=False, key=lambda s: pd.to_datetime(s, errors="coerce"))
        except Exception:
            pass

    if title:
        st.subheader(title)
    show_dataframe(df)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="matches", key_prefix=f"{key_prefix}-matches")

    return df


# ------------------------------
# Tableaux de quarts-temps
# ------------------------------

def quarters_table(
    quarters: Iterable[Any],
    home_label: str,
    away_label: str,
    title: str = "🧮 Détail par quart-temps",
    show_download: bool = True,
    key_prefix: str = "quarters",
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for q in quarters or []:
        rows.append({
            "Q": _get(q, "q"),
            f"{home_label} G": _get(q, "home_goals", 0),
            f"{home_label} B": _get(q, "home_behinds", 0),
            f"{home_label} P": _get(q, "home_points", 0),
            f"{away_label} G": _get(q, "away_goals", 0),
            f"{away_label} B": _get(q, "away_behinds", 0),
            f"{away_label} P": _get(q, "away_points", 0),
        })

    df = pd.DataFrame(rows)

    # Ligne total si calcul possible
    try:
        sums = sum_quarters_match(list(quarters or []))
        hg, hb, hp = sums["home"]
        ag, ab, ap = sums["away"]
        total_row = {
            "Q": "Total",
            f"{home_label} G": hg,
            f"{home_label} B": hb,
            f"{home_label} P": hp,
            f"{away_label} G": ag,
            f"{away_label} B": ab,
            f"{away_label} P": ap,
        }
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    except Exception:
        pass

    if title:
        st.subheader(title)
    show_dataframe(df)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="quarters", key_prefix=f"{key_prefix}-quarters")

    return df


# ------------------------------
# Tableaux de stats joueurs
# ------------------------------

def players_stats_table_view(
    pstats: Iterable[Any],
    team_label: str = "Mon équipe",
    show_total: bool = True,
    show_download: bool = False,
    key_prefix: str = "players",
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for ps in pstats or []:
        rows.append({
            "Joueur": _get(ps, "player_name"),
            "Buts":   int(_get(ps, "goals", 0) or 0),
            "Behinds":int(_get(ps, "behinds", 0) or 0),
            "Points": int(_get(ps, "points", 0) or 0),
        })

    df = pd.DataFrame(rows)

    if show_total and not df.empty:
        total_row = {
            "Joueur": f"Total {team_label}",
            "Buts":   int(df["Buts"].fillna(0).sum()),
            "Behinds":int(df["Behinds"].fillna(0).sum()),
            "Points": int(df["Points"].fillna(0).sum()),
        }
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

    show_dataframe(df)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="players", key_prefix=f"{key_prefix}-players")

    return df


# ------------------------------
# En-tête compact de match
# ------------------------------

def match_header(match: Any, show_scoreline: bool = True) -> None:
    """
    Affiche un en-tête résumant le match (Date – Home vs Away – score).
    """
    d = _get(match, "date")
    saison = _get(match, "season_id")
    home = _get(match, "home_club", "Home")
    away = _get(match, "away_club", "Away")
    venue = _get(match, "venue")

    left = f"**{home}** vs **{away}**"

    if show_scoreline:
        try:
            sh, sa = scoreline_home_away(match)
            right = f"{sh} – {sa}"
        except Exception:
            right = f"({_get(match, 'total_home_points', '?')}) – ({_get(match, 'total_away_points', '?')})"
    else:
        right = ""

    meta_parts = []
    if isinstance(d, (date, str)) and d:
        meta_parts.append(str(d))
    if saison:
        meta_parts.append(f"Saison {saison}")
    if venue:
        meta_parts.append(str(venue))
    meta = " · ".join(meta_parts)

    if meta:
        st.caption(meta)
    st.markdown(f"{left} &nbsp;&nbsp; {right}")
# ------------------------------