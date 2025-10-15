# Tables/metrics réutilisables
# app/ui/table.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from encodings.idna import ace_prefix
from typing import Iterable, List, Dict, Any, Optional
from datetime import date

import pandas as pd
import streamlit as st

from core.scoring import (
    winner,
    margin,
    scoreline_home_away,
    sum_quarters_match,
    format_scoreline,
)

# ------------------------------
# Utils d'affichage génériques
# ------------------------------

def _download_row(df: pd.DataFrame, filename_prefix: str, key_prefix: str = "dl") -> None:
    """Affiche une rangée de 2 boutons de téléchargement (CSV/JSON)."""
    csv = df.to_csv(index=False).encode("utf-8")
    jsonb = df.to_json(orient="records").encode("utf-8")
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Télécharger CSV",
        data=csv,
        file_name=f"{filename_prefix}.csv",
        mime="text/csv",
        key=f"{key_prefix}-csv",            # ✅ clé unique
    )
    c2.download_button(
        "⬇️ Télécharger JSON",
        data=jsonb,
        file_name=f"{filename_prefix}.json",
        mime="application/json",
        key=f"{key_prefix}-json",           # ✅ clé unique
    )

def show_dataframe(
    df: pd.DataFrame,
    caption: Optional[str] = None,
    use_container_width: bool = True,
    key: Optional[str] = None,
) -> None:
    """
    Wrapper Streamlit pour afficher un DataFrame avec quelques réglages commonsense.
    """
    if caption:
        st.caption(caption)
    st.dataframe(df, use_container_width=use_container_width, hide_index=True, key=key)


# ------------------------------
# Tableaux de matches
# ------------------------------

def matches_table(rows, title: str = None, show_download: bool = False, key_prefix: str = "matches"):
    df = pd.DataFrame([{
        "ID": getattr(m, "id", None) if hasattr(m, "id") else m.get("id"),
        "Date": getattr(m, "date", None) if hasattr(m, "date") else m.get("date"),
        "Saison": getattr(m, "season_id", None) if hasattr(m, "season_id") else m.get("season_id"),
        "Domicile": getattr(m, "home_club", None) if hasattr(m, "home_club") else m.get("home_club"),
        "Extérieur": getattr(m, "away_club", None) if hasattr(m, "away_club") else m.get("away_club"),
        "Pts Dom": getattr(m, "total_home_points", None) if hasattr(m, "total_home_points") else m.get("total_home_points"),
        "Pts Ext": getattr(m, "total_away_points", None) if hasattr(m, "total_away_points") else m.get("total_away_points"),
        "Lieu": getattr(m, "venue", None) if hasattr(m, "venue") else m.get("venue"),
    } for m in rows or []])

    if title:
        st.subheader(title)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="matches", key_prefix=f"{key_prefix}-matches")



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
    """
    Affiche un tableau des quarts : Q, HG, HB, HP, AG, AB, AP + ligne Total.
    """
    rows: List[Dict[str, Any]] = []
    for q in quarters or []:
        rows.append({
            "Q": getattr(q, "q", None),
            f"{home_label} G": getattr(q, "home_goals", None),
            f"{home_label} B": getattr(q, "home_behinds", None),
            f"{home_label} P": getattr(q, "home_points", None),
            f"{away_label} G": getattr(q, "away_goals", None),
            f"{away_label} B": getattr(q, "away_behinds", None),
            f"{away_label} P": getattr(q, "away_points", None),
        })

    df = pd.DataFrame(rows)

    # Ligne total si possible
    try:
        sums = sum_quarters_match(quarters or [])
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
    team_label: str = "Toulouse",
    show_total: bool = True,
    show_download: bool = False,
    key_prefix: str = "players",
) -> pd.DataFrame:
    """
    Affiche le tableau des stats joueurs : Joueur, Buts, Behinds, Points.
    Optionnellement ajoute une ligne Total et des boutons de téléchargement.
    """
    rows: List[Dict[str, Any]] = []
    for ps in pstats or []:
        rows.append({
            "Joueur": getattr(ps, "player_name", None) if hasattr(ps, "player_name") else ps.get("player_name"),
            "Buts":   getattr(ps, "goals", None)       if hasattr(ps, "goals")       else ps.get("goals"),
            "Behinds":getattr(ps, "behinds", None)     if hasattr(ps, "behinds")     else ps.get("behinds"),
            "Points": getattr(ps, "points", None)      if hasattr(ps, "points")      else ps.get("points"),
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

    st.dataframe(df, use_container_width=True, hide_index=True)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="players", key_prefix=f"{key_prefix}-players")

    return df


# ------------------------------
# Aides d'affichage compacts
# ------------------------------

def match_header(match: Any, show_scoreline: bool = True) -> None:
    """
    Affiche un petit en-tête résumant le match (Date – Home vs Away – score).
    """
    d = getattr(match, "date", None)
    saison = getattr(match, "season_id", None)
    home = getattr(match, "home_club", "Home")
    away = getattr(match, "away_club", "Away")
    venue = getattr(match, "venue", None)

    left = f"**{home}** vs **{away}**"
    right = ""
    if show_scoreline:
        try:
            sh, sa = scoreline_home_away(match)
            right = f"{sh} – {sa}"
        except Exception:
            right = f"({getattr(match, 'total_home_points', '?')}) – ({getattr(match, 'total_away_points', '?')})"

    meta = " · ".join([str(d) if isinstance(d, (date, str)) and d else "", f"Saison {saison}" if saison else "", venue or ""]).strip(" ·")
    if meta:
        st.caption(meta)
    st.markdown(f"{left} &nbsp;&nbsp; {right}")
# ---------- FIN ----------