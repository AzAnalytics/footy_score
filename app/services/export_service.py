# (optionnel) Export PDF/CSV
# app/services/export_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, Any, Dict, List, Tuple, Optional
from types import SimpleNamespace as _NS
from io import BytesIO

import pandas as pd


# ============================================================
# Normalisation de structures (dict -> objet à attributs)
# ============================================================

def _as_obj(row: Any) -> Any:
    """Accepte dict ou objet ; retourne un objet à attributs."""
    if isinstance(row, dict):
        return _NS(**row)
    return row


# ============================================================
# DataFrames standardisés
# ============================================================

def df_from_matches(rows: Iterable[Any]) -> pd.DataFrame:
    """
    Construit un DataFrame de matches avec des colonnes standard :
    ['ID','Date','Saison','Domicile','Extérieur','Points Domicile','Points Extérieur','Lieu']
    """
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        m = _as_obj(r)
        out.append({
            "ID": getattr(m, "id", None),
            "Date": getattr(m, "date", None),
            "Saison": getattr(m, "season_id", None),
            "Domicile": getattr(m, "home_club", None),
            "Extérieur": getattr(m, "away_club", None),
            "Points Domicile": getattr(m, "total_home_points", None),
            "Points Extérieur": getattr(m, "total_away_points", None),
            "Lieu": getattr(m, "venue", None),
        })
    df = pd.DataFrame(out)
    # Tri du plus récent au plus ancien si Date présente
    if not df.empty and "Date" in df.columns:
        try:
            df = df.sort_values("Date", ascending=False)
        except Exception:
            pass
    return df


def df_from_quarters(
    quarters: Iterable[Any],
    home_label: str,
    away_label: str,
    with_total: bool = True,
) -> pd.DataFrame:
    """
    DataFrame des quarts-temps :
    Colonnes: ['Q', f'{home} G','{home} B','{home} P', f'{away} G','{away} B','{away} P']
    Ajoute une ligne 'Total' si with_total=True.
    """
    rows: List[Dict[str, Any]] = []
    hg = hb = hp = ag = ab = ap = 0

    for q in quarters or []:
        o = _as_obj(q)
        hG = getattr(o, "home_goals", 0) or 0
        hB = getattr(o, "home_behinds", 0) or 0
        hP = getattr(o, "home_points", 0) or 0
        aG = getattr(o, "away_goals", 0) or 0
        aB = getattr(o, "away_behinds", 0) or 0
        aP = getattr(o, "away_points", 0) or 0

        rows.append({
            "Q": getattr(o, "q", None),
            f"{home_label} G": hG,
            f"{home_label} B": hB,
            f"{home_label} P": hP,
            f"{away_label} G": aG,
            f"{away_label} B": aB,
            f"{away_label} P": aP,
        })

        hg += hG; hb += hB; hp += hP
        ag += aG; ab += aB; ap += aP

    df = pd.DataFrame(rows)
    if with_total and not df.empty:
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
    return df


def df_from_player_stats(player_stats: Iterable[Any], team_label: str = "Toulouse", with_total: bool = True) -> pd.DataFrame:
    """
    DataFrame des stats joueurs :
    Colonnes: ['Joueur','Goals','Behinds','Points']
    Ajoute une ligne 'Total <team_label>' si with_total=True.
    """
    rows: List[Dict[str, Any]] = []
    for r in player_stats or []:
        o = _as_obj(r)
        name = getattr(o, "player_name", None)
        rows.append({
            "Joueur": name,
            "Goals": int(getattr(o, "goals", 0) or 0),
            "Behinds": int(getattr(o, "behinds", 0) or 0),
            "Points": int(getattr(o, "points", 0) or 0),
        })
    df = pd.DataFrame(rows)
    if with_total and not df.empty:
        total_row = {
            "Joueur": f"Total {team_label}",
            "Goals": int(df["Goals"].sum()),
            "Behinds": int(df["Behinds"].sum()),
            "Points": int(df["Points"].sum()),
        }
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    return df


# ============================================================
# Exports binaires
# ============================================================

def to_csv_bytes(df: pd.DataFrame, sep: str = ",", index: bool = False, encoding: str = "utf-8") -> bytes:
    """Encode un DataFrame en CSV (bytes)."""
    return df.to_csv(index=index, sep=sep).encode(encoding)


def to_json_bytes(df: pd.DataFrame, orient: str = "records", force_ascii: bool = False) -> bytes:
    """Encode un DataFrame en JSON (bytes)."""
    return df.to_json(orient=orient, force_ascii=force_ascii).encode("utf-8")


def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """
    Crée un classeur Excel en mémoire avec une feuille par entrée du dict.
    `sheets` : {'Matches': df1, 'Quarters': df2, ...}
    """
    bio = BytesIO()
    # engine='xlsxwriter' ou 'openpyxl' selon tes deps ; pandas choisira si dispo.
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            # Sécurité : nom d’onglet max 31 chars
            safe_name = str(name)[:31] if name else "Sheet"
            (df or pd.DataFrame()).to_excel(writer, sheet_name=safe_name, index=False)
    bio.seek(0)
    return bio.getvalue()


# ============================================================
# Bundles d’export
# ============================================================

def build_match_detail_dataframes(detail: Dict[str, Any], team_label: str = "Toulouse") -> Dict[str, pd.DataFrame]:
    """
    À partir d’un `detail` (dict retourné par get_match), produit les DataFrames :
    - 'Match' (1 ligne)
    - 'Quarters'
    - 'Players'
    """
    # Feuille Match (1 ligne)
    match_df = df_from_matches([detail])

    # Feuille Quarters
    home = detail.get("home_club") or "Home"
    away = detail.get("away_club") or "Away"
    quarters_df = df_from_quarters(detail.get("quarters", []) or [], home_label=home, away_label=away, with_total=True)

    # Feuille Players
    players_df = df_from_player_stats(detail.get("player_stats", []) or [], team_label=team_label, with_total=True)

    return {
        "Match": match_df,
        "Quarters": quarters_df,
        "Players": players_df,
    }


def build_matches_overview_dataframe(rows: Iterable[Any]) -> pd.DataFrame:
    """
    DataFrame synthétique multi-matchs (utile pour export global).
    """
    return df_from_matches(rows)


def export_match_bundle_excel(detail: Dict[str, Any], team_label: str = "Toulouse") -> Tuple[bytes, str]:
    """
    Construit un fichier Excel (bytes) pour un match : onglets Match / Quarters / Players.
    Retourne (bytes, suggested_filename).
    """
    dfs = build_match_detail_dataframes(detail, team_label=team_label)
    data = to_excel_bytes(dfs)
    mid = detail.get("id", "match")
    fname = f"match_{mid}.xlsx"
    return data, fname


def export_matches_overview_excel(rows: Iterable[Any]) -> Tuple[bytes, str]:
    """
    Construit un Excel (bytes) avec un onglet 'Matches' listant tous les matches.
    """
    df = build_matches_overview_dataframe(rows)
    data = to_excel_bytes({"Matches": df})
