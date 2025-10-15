# app/pages/2_📚_Historique.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from types import SimpleNamespace as _NS
from datetime import date as _date
import pandas as pd

from services.auth_service import require_login, current_user
from core.repos.matches_repo import (
    list_matches,
    list_matches_for_team,
    get_match,
    update_match_fields,
    replace_player_stats_for_match,
)

from ui.nav import sidebar_menu
from ui.tables import matches_table, match_header, quarters_table, players_stats_table_view

# ---------------------------
# Page + helpers
# ---------------------------
st.set_page_config(page_title="Historique", page_icon="📚")
st.title("📚 Historique des matchs")

u = sidebar_menu()

def _auth_ctx() -> dict:
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": (u.get("team_name") or "").strip(),
        "is_admin": bool(u.get("is_admin")),
    }

def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf(tok: str | None) -> bool:
    return bool(tok and tok == st.session_state.get("csrf_token"))

user = require_login()
caller = _auth_ctx()
csrf = _ensure_csrf()

team = caller["team_name"]

# ---------------------------
# Liste des matchs (filtrée)
# ---------------------------
if team and not caller["is_admin"]:
    rows = list_matches_for_team(team, 100, user_ctx=caller)
    st.caption(f"Filtrage par équipe : **{team}**")
    key_prefix_main = "hist-main-team"
else:
    # Admin : listing global (toujours avec user_ctx)
    rows = list_matches(100, user_ctx=caller)
    st.caption("Affichage global.")
    key_prefix_main = "hist-main-all"

st.markdown("---")

if not rows:
    st.info("Aucun match enregistré.")
    st.stop()

# ---- Vue synthétique : tableau ----
match_objs = [_NS(**m) for m in rows]
matches_table(
    match_objs,
    title="📜 Récapitulatif des matchs",
    show_download=True,
    key_prefix=key_prefix_main,
)

# ---------------------------
# Détail par match
# ---------------------------
for m in rows:
    header = f"{m['date']} — {m['home_club']} {m['total_home_points']} – {m['total_away_points']} {m['away_club']}"
    with st.expander(header, expanded=False):
        st.caption(f"Saison {m['season_id']} • Lieu : {m.get('venue') or '—'} • ID: {m['id']}")

        # Détail (quarts + stats) — protégé par user_ctx
        detail = get_match(m["id"], user_ctx=caller)
        if not detail:
            st.warning("Détails indisponibles ou non autorisés.")
            continue

        # Objet match léger pour l'UI
        match_obj = _NS(
            id=detail.get("id"),
            date=detail.get("date"),
            season_id=detail.get("season_id"),
            home_club=detail.get("home_club"),
            away_club=detail.get("away_club"),
            venue=detail.get("venue"),
            total_home_points=detail.get("total_home_points"),
            total_away_points=detail.get("total_away_points"),
            total_home_goals=detail.get("total_home_goals"),
            total_home_behinds=detail.get("total_home_behinds"),
            total_away_goals=detail.get("total_away_goals"),
            total_away_behinds=detail.get("total_away_behinds"),
        )

        # En-tête match compact (utilise scoreline si dispo)
        match_header(match_obj, show_scoreline=True)

        # ✏️ Modifier ce match
        with st.expander("✏️ Modifier ce match", expanded=False):
            _d = detail

            c1, c2 = st.columns(2)
            home_edit = c1.text_input("🏠 Domicile", value=_d.get("home_club") or "", key=f"home-{m['id']}")
            away_edit = c2.text_input("🛫 Extérieur", value=_d.get("away_club") or "", key=f"away-{m['id']}")

            venue_edit = st.text_input("📍 Lieu", value=_d.get("venue") or "", key=f"venue-{m['id']}")

            c3, c4 = st.columns(2)
            try:
                parsed_date = _date.fromisoformat(str(_d.get("date")))
            except Exception:
                parsed_date = _date.today()
            date_edit = c3.date_input("📅 Date", value=parsed_date, key=f"date-{m['id']}")
            season_edit = c4.text_input("🗓️ Saison", value=str(_d.get("season_id") or ""), key=f"season-{m['id']}")

            c5, c6 = st.columns(2)
            thp_edit = c5.number_input("🔢 Points domicile", min_value=0, value=int(_d.get("total_home_points") or 0), key=f"thp-{m['id']}")
            tap_edit = c6.number_input("🔢 Points extérieur", min_value=0, value=int(_d.get("total_away_points") or 0), key=f"tap-{m['id']}")

            # CSRF caché pour ce bloc
            st.text_input("CSRF", value=csrf, type="password", key=f"csrf-upd-{m['id']}", label_visibility="collapsed")
            save_btn = st.button("💾 Enregistrer", key=f"save-match-{m['id']}")

            if save_btn:
                if not _check_csrf(st.session_state.get(f"csrf-upd-{m['id']}")):
                    st.error("CSRF invalide.")
                else:
                    ok = update_match_fields(
                        m["id"],
                        season_id=season_edit,
                        date=date_edit,
                        venue=venue_edit,
                        home_club=home_edit,
                        away_club=away_edit,
                        total_home_points=thp_edit,
                        total_away_points=tap_edit,
                        user_ctx=caller,
                    )
                    if ok:
                        st.success("Match mis à jour ✅")
                        st.rerun()
                    else:
                        st.error("Échec de la mise à jour (droits ou validation).")

        # Quarts-temps
        qs = detail.get("quarters", []) or []
        if qs:
            st.markdown("### 🧮 Quarts-temps")
            q_objs = [_NS(**q) for q in qs]
            quarters_table(
                q_objs,
                home_label=match_obj.home_club,
                away_label=match_obj.away_club,
                show_download=True,
                key_prefix=f"match-{m['id']}-q",
            )
        else:
            st.info("Aucun quart-temps enregistré pour ce match.")

        # Stats joueurs (pour l’équipe du user si connue, sinon neutre)
        pstats = detail.get("player_stats", []) or []
        team_label = team or "Votre équipe"
        if pstats:
            st.markdown(f"### 👥 Stats joueurs ({team_label})")
            players_stats_table_view(
                pstats,
                team_label=team_label,
                show_total=True,
                show_download=True,
                key_prefix=f"match-{m['id']}-p",
            )
        else:
            st.info("Aucune stat joueur enregistrée pour ce match.")

        # 📝 Corriger stats joueurs (édition)
        st.markdown(f"### 📝 Corriger stats joueurs ({team_label})")
        df_ps = pd.DataFrame([
            {
                "player_name": ps.get("player_name"),
                "goals": int(ps.get("goals") or 0),
                "behinds": int(ps.get("behinds") or 0),
                "points": 6 * int(ps.get("goals") or 0) + int(ps.get("behinds") or 0),
            } for ps in pstats
        ])

        st.caption("Modifie **buts** et **behinds** ; les **points** sont recalculés automatiquement à l’enregistrement.")
        edited = st.data_editor(
            df_ps,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "player_name": st.column_config.TextColumn("Joueur", required=True),
                "goals": st.column_config.NumberColumn("Buts", min_value=0, step=1),
                "behinds": st.column_config.NumberColumn("Behinds", min_value=0, step=1),
                "points": st.column_config.NumberColumn("Points (auto)", disabled=True),
            },
            key=f"ps-edit-{m['id']}",
        )

        # Recalcul local pour affichage
        edited["points"] = (edited["goals"].fillna(0).astype(int) * 6 + edited["behinds"].fillna(0).astype(int))
        sum_players = int(edited["points"].fillna(0).sum())

        # Score déclaré côté de l’équipe du user (si on peut déterminer le côté)
        declared = None
        side_for_user = None
        if team:
            if match_obj.home_club == team:
                side_for_user = "home"; declared = int(match_obj.total_home_points or 0)
            elif match_obj.away_club == team:
                side_for_user = "away"; declared = int(match_obj.total_away_points or 0)

        if declared is not None:
            if sum_players == declared:
                st.success(f"Somme points joueurs = **{sum_players}** (OK, égal au score déclaré **{declared}**).")
            else:
                st.warning(f"Somme points joueurs = **{sum_players}** ≠ score déclaré **{declared}**.")

        col_left, col_right = st.columns(2)
        with col_left:
            update_totals = st.checkbox(
                "Ajuster aussi le score du match côté mon équipe",
                value=(declared is not None and sum_players != declared),
                key=f"ps-ajust-{m['id']}",
                help="Aligne le total du match (home/away) sur la somme des points joueurs saisis.",
            )
        with col_right:
            # CSRF pour la sauvegarde
            st.text_input("CSRF", value=csrf, type="password", key=f"csrf-ps-{m['id']}", label_visibility="collapsed")
            save_ps = st.button("💾 Enregistrer les stats joueurs", key=f"ps-save-{m['id']}")

        if save_ps:
            if not _check_csrf(st.session_state.get(f"csrf-ps-{m['id']}")):
                st.error("CSRF invalide.")
            else:
                rows_to_save = []
                for _, r in edited.iterrows():
                    name = (str(r.get("player_name") or "").strip())
                    if not name:
                        continue
                    rows_to_save.append({
                        "player_name": name,
                        "goals": int(r.get("goals") or 0),
                        "behinds": int(r.get("behinds") or 0),
                    })

                if not rows_to_save:
                    st.error("Aucune ligne valide à enregistrer.")
                else:
                    # Choix du côté à réaligner (si demandé et si déterminable)
                    recalc_side = None
                    if update_totals and side_for_user in {"home", "away"}:
                        recalc_side = side_for_user

                    ok = replace_player_stats_for_match(
                        m["id"],
                        rows_to_save,
                        recalc_match_totals_side=recalc_side,
                        user_ctx=caller,
                    )
                    if ok:
                        st.success("Stats joueurs mises à jour ✅")
                        st.rerun()
                    else:
                        st.error("Échec de la mise à jour des stats joueurs (droits ou validation).")

    st.markdown("---")
