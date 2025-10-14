# Tables/metrics réutilisables
# app/ui/table.py
# -*- coding: utf-8 -*-
from __future__ import annotations
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

def _download_row(df: pd.DataFrame, filename_prefix: str) -> None:
    """
    Ajoute deux boutons de téléchargement (CSV/JSON) sous le tableau courant.
    """
    c1, c2 = st.columns(2)
    csv = df.to_csv(index=False).encode("utf-8")
    json = df.to_json(orient="records", force_ascii=False).encode("utf-8")
    c1.download_button("⬇️ Télécharger CSV", data=csv, file_name=f"{filename_prefix}.csv", mime="text/csv")
    c2.download_button("⬇️ Télécharger JSON", data=json, file_name=f"{filename_prefix}.json", mime="application/json")


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

def matches_table(matches: Iterable[Any], title: str = "📜 Historique des matches", show_download: bool = True) -> pd.DataFrame:
    """
    Affiche un tableau récapitulatif d'une liste de Match.
    Colonnes : Date, Saison, Domicile, Extérieur, Score, Vainqueur, Écart, Lieu, ID
    """
    rows: List[Dict[str, Any]] = []
    for m in matches or []:
        try:
            sh, sa = scoreline_home_away(m)
        except Exception:
            # fallback minimal si G/B pas dispo
            sh, sa = f"({getattr(m, 'total_home_points', None)})", f"({getattr(m, 'total_away_points', None)})"

        try:
            res = winner(m)
        except Exception:
            res = None

        try:
            mg = margin(m)
        except Exception:
            mg = None

        rows.append({
            "Date": getattr(m, "date", None),
            "Saison": getattr(m, "season_id", None),
            "Domicile": getattr(m, "home_club", None),
            "Extérieur": getattr(m, "away_club", None),
            "Score": f"{sh}  –  {sa}",
            "Vainqueur": {"home": getattr(m, "home_club", None), "away": getattr(m, "away_club", None), "draw": "Égalité"}.get(res, None),
            "Écart": mg,
            "Lieu": getattr(m, "venue", None),
            "ID": getattr(m, "id", None),
        })

    df = pd.DataFrame(rows)
    # Tri récent → ancien par défaut si la colonne Date est présente
    if not df.empty and "Date" in df.columns:
        df = df.sort_values("Date", ascending=False)

    if title:
        st.subheader(title)
    show_dataframe(df)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="matches")

    return df


# ------------------------------
# Tableaux de quarts-temps
# ------------------------------

def quarters_table(quarters: Iterable[Any], home_label: str, away_label: str, title: str = "🧮 Détail par quart-temps", show_download: bool = True) -> pd.DataFrame:
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
        _download_row(df, filename_prefix="quarters")

    return df


# ------------------------------
# Tableaux de stats joueurs
# ------------------------------

def players_stats_table_view(
    player_stats: Iterable[Any],
    team_label: str = "Toulouse",
    title: str = "👥 Stats joueurs",
    show_total: bool = True,
    show_download: bool = True,
) -> pd.DataFrame:
    """
    Affiche un tableau des stats joueurs : Joueur, Goals, Behinds, Points (+ Total).
    `player_stats` peut être une liste de PlayerStat ou de dicts.
    """
    rows: List[Dict[str, Any]] = []
    for r in player_stats or []:
        # support PlayerStat obj ou dict
        name = getattr(r, "player_name", None) or (r.get("player_name") if isinstance(r, dict) else None) or ""
        goals = getattr(r, "goals", None) if not isinstance(r, dict) else r.get("goals")
        behinds = getattr(r, "behinds", None) if not isinstance(r, dict) else r.get("behinds")
        points = getattr(r, "points", None) if not isinstance(r, dict) else r.get("points")
        rows.append({
            "Joueur": name,
            "Goals": goals or 0,
            "Behinds": behinds or 0,
            "Points": points or 0,
        })

    df = pd.DataFrame(rows)

    if show_total and not df.empty:
        total_row = {
            "Joueur": f"Total {team_label}",
            "Goals": int(df["Goals"].sum()),
            "Behinds": int(df["Behinds"].sum()),
            "Points": int(df["Points"].sum()),
        }
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

    if title:
        st.subheader(title)
    show_dataframe(df)

    if show_download and not df.empty:
        _download_row(df, filename_prefix="players_stats")

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