# Petits composants (inputs joueurs, score)
# app/ui/inputs.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional

import streamlit as st
from core.models import calc_points


def _slug(s: str) -> str:
    """Slug simple pour générer des clés Streamlit stables."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9._\-]", "", s)
    return s or "x"


# -----------------------------
# Score (buts/behinds -> points)
# -----------------------------
def score_inputs(label: str, *, key_prefix: Optional[str] = None) -> Dict[str, int]:
    """
    Saisie compacte d’un score: buts, behinds -> points (affichés).
    Retourne {"goals": int, "behinds": int, "points": int}
    """
    kp = key_prefix or f"score-{_slug(label)}"
    c1, c2, c3 = st.columns(3)
    g = c1.number_input(f"{label} • Buts", min_value=0, step=1, key=f"{kp}-g")
    b = c2.number_input(f"{label} • Behinds", min_value=0, step=1, key=f"{kp}-b")
    p = calc_points(int(g), int(b))
    c3.metric(f"{label} • Points", p)
    return {"goals": int(g), "behinds": int(b), "points": int(p)}


# -------------------------------------------
# Table d’édition des stats joueurs (data_editor)
# -------------------------------------------
def players_stat_table(
    default_names: List[str],
    *,
    team_label: str = "Mon équipe",
    key_prefix: Optional[str] = None,
) -> List[Dict]:
    """
    Éditeur de stats joueurs (nom, buts, behinds) avec recalcul automatique des points.
    - default_names: liste de noms proposée initialement
    - team_label: intitulé d’équipe (affichage)
    - key_prefix: pour stabiliser l’état du widget si plusieurs tables coexistent

    Retourne une liste de dicts: [{"player_name", "goals", "behinds", "points"}, ...]
    """
    import pandas as pd  # import local pour limiter les dépendances globales

    kp = key_prefix or f"pstable-{_slug(team_label)}"

    st.caption(f"Joueurs ({team_label}) — ajoute, supprime ou modifie les lignes ci-dessous.")

    # État initial (une seule fois) pour préserver les saisies lors des reruns
    state_key = f"{kp}-df"
    if state_key not in st.session_state:
        # normalise les noms (trim, non vides, uniques dans l’ordre d’apparition)
        seen = set()
        init_rows = []
        for raw in default_names or []:
            name = (str(raw or "").strip())
            if not name:
                continue
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            init_rows.append({"player_name": name, "goals": 0, "behinds": 0, "points": 0})
        if not init_rows:
            init_rows = [{"player_name": "", "goals": 0, "behinds": 0, "points": 0}]
        st.session_state[state_key] = pd.DataFrame(init_rows)

    df = st.session_state[state_key].copy()

    # Config de colonnes
    config = {
        "player_name": st.column_config.TextColumn("Joueur", required=True, width="medium"),
        "goals": st.column_config.NumberColumn("Buts", min_value=0, step=1, width="small"),
        "behinds": st.column_config.NumberColumn("Behinds", min_value=0, step=1, width="small"),
        "points": st.column_config.NumberColumn("Points (auto)", disabled=True, width="small"),
    }

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=config,
        key=f"{kp}-editor",
    )

    # Recalcul des points et nettoyage
    edited = edited.fillna({"player_name": "", "goals": 0, "behinds": 0})
    # Coercition sûre
    try:
        edited["goals"] = edited["goals"].astype(int).clip(lower=0)
        edited["behinds"] = edited["behinds"].astype(int).clip(lower=0)
    except Exception:
        # fallback si types étranges
        edited["goals"] = edited["goals"].apply(lambda x: int(x) if str(x).isdigit() else 0)
        edited["behinds"] = edited["behinds"].apply(lambda x: int(x) if str(x).isdigit() else 0)

    edited["points"] = edited["goals"] * 6 + edited["behinds"]
    st.session_state[state_key] = edited  # persiste l’état pour les prochains reruns

    # Avertissements utiles (doublons, vides)
    names_norm = [(str(n or "").strip().lower()) for n in edited["player_name"].tolist()]
    non_empty = [i for i, n in enumerate(names_norm) if n]
    empties = [i for i, n in enumerate(names_norm) if not n]
    dup_set = {n for n in names_norm if n and names_norm.count(n) > 1}

    if dup_set:
        st.warning("Noms en doublon détectés : " + ", ".join(sorted(dup_set)))
    if empties:
        st.info("Des lignes sans nom existent — elles seront ignorées à l’enregistrement.")

    # Total affiché
    total_pts = int(edited["points"].sum() if not edited.empty else 0)
    st.caption(f"**Total points {team_label} : {total_pts}**")

    # Conversion en liste de dicts (en ignorant les lignes vides)
    out: List[Dict] = []
    for _, r in edited.iterrows():
        name = (str(r.get("player_name") or "").strip())
        if not name:
            continue
        out.append({
            "player_name": name,
            "goals": int(r.get("goals") or 0),
            "behinds": int(r.get("behinds") or 0),
            "points": int(r.get("points") or 0),
        })

    return out
# -----------------------------