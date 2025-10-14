# Petits composants (inputs joueurs, score)
# app/ui/inputs.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from typing import Dict, List
from app.core.models import calc_points

def score_inputs(label: str) -> Dict[str, int]:
    c1, c2, c3 = st.columns(3)
    g = c1.number_input(f"{label} • Buts", min_value=0, step=1, key=f"g_{label}")
    b = c2.number_input(f"{label} • Behinds", min_value=0, step=1, key=f"b_{label}")
    p = calc_points(int(g), int(b))
    c3.metric(f"{label} • Points", p)
    return {"goals": int(g), "behinds": int(b), "points": p}

def players_stat_table(default_names: List[str]) -> List[Dict]:
    st.caption("Joueurs Toulouse (un par ligne) — tu peux éditer la liste ci-dessous.")
    names_text = st.text_area("Liste des joueurs", value="\n".join(default_names), height=160)
    rows: List[Dict] = []
    for raw in [n.strip() for n in names_text.splitlines() if n.strip()]:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        with c1: st.text_input("Nom", value=raw, key=f"name_{raw}", disabled=True)
        g = c2.number_input("Buts", min_value=0, step=1, key=f"pg_{raw}")
        b = c3.number_input("Behinds", min_value=0, step=1, key=f"pb_{raw}")
        pts = calc_points(int(g), int(b))
        with c4: st.metric("Points", pts)
        rows.append({"player_name": raw, "goals": int(g), "behinds": int(b), "points": pts})
    return rows
