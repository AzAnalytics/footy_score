# (optionnel) Export PDF/CSV
# app/services/export_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, Any, Dict, List, Tuple, Optional
from types import SimpleNamespace as _NS
from io import BytesIO
import re

import pandas as pd
import numpy as np


# ============================================================
# Normalisation de structures (dict -> objet à attributs)
# ============================================================

def _as_obj(row: Any) -> Any:
    """Accepte dict ou objet ; retourne un objet à attributs."""
    if isinstance(row, dict):
        return _NS(**row)
    return row


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return default
        return int(x)
    except Exception:
        return default


def _safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    s = str(x)
    return s


def _to_date_str(x: Any) -> Any:
    """Retourne une date ISO 'YYYY-MM-DD' si possible, sinon la valeur d'origine."""
    try:
        # pandas/py datetime -> str
        return pd.to_datetime(x).date().isoformat()
    except Exception:
        return x


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
            "Date": _to_date_str(getattr(m, "date", None)),
            "Saison": _safe_str(getattr(m, "season_id", None)),
            "Domicile": _safe_str(getattr(m, "home_club", None)),
            "Extérieur": _safe_str(getattr(m, "away_club", None)),
            "Points Domicile": _safe_int(getattr(m, "total_home_points", None)),
            "Points Extérieur": _safe_int(getattr(m, "total_away_points", None)),
            "Lieu": _safe_str(getattr(m, "venue", None)),
        })
    df = pd.DataFrame(out)
    # Tri du plus récent au plus ancien si Date présente
    if not df.empty and "Date" in df.columns:
        try:
            df = df.sort_values("Date", ascending=False, key=lambda s: pd.to_datetime(s, errors="coerce"))
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
        hG = _safe_int(getattr(o, "home_goals", 0))
        hB = _safe_int(getattr(o, "home_behinds", 0))
        hP = _safe_int(getattr(o, "home_points", 0))
        aG = _safe_int(getattr(o, "away_goals", 0))
        aB = _safe_int(getattr(o, "away_behinds", 0))
        aP = _safe_int(getattr(o, "away_points", 0))

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


def df_from_player_stats(
    player_stats: Iterable[Any],
    team_label: Optional[str] = None,
    with_total: bool = True
) -> pd.DataFrame:
    """
    DataFrame des stats joueurs :
    Colonnes: ['Joueur','Goals','Behinds','Points']
    Ajoute une ligne 'Total <team_label>' si with_total=True et team_label fourni.
    """
    rows: List[Dict[str, Any]] = []
    for r in player_stats or []:
        o = _as_obj(r)
        rows.append({
            "Joueur": _safe_str(getattr(o, "player_name", None)),
            "Goals": _safe_int(getattr(o, "goals", 0)),
            "Behinds": _safe_int(getattr(o, "behinds", 0)),
            "Points": _safe_int(getattr(o, "points", 0)),
        })
    df = pd.DataFrame(rows)
    if with_total and not df.empty:
        label = f"Total {team_label}" if team_label else "Total"
        total_row = {
            "Joueur": label,
            "Goals": int(df["Goals"].sum()),
            "Behinds": int(df["Behinds"].sum()),
            "Points": int(df["Points"].sum()),
        }
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    return df


# ============================================================
# Exports binaires
# ============================================================

def to_csv_bytes(
    df: pd.DataFrame,
    sep: str = ",",
    index: bool = False,
    encoding: str = "utf-8",
    add_bom: bool = False,
    lineterminator: str = "\n",
) -> bytes:
    """
    Encode un DataFrame en CSV (bytes).
    - add_bom=True si vous ciblez Excel Windows (UTF-8-SIG).
    """
    csv_str = df.to_csv(index=index, sep=sep, lineterminator=lineterminator)
    data = csv_str.encode("utf-8-sig" if add_bom else encoding)
    return data


def to_json_bytes(df: pd.DataFrame, orient: str = "records", force_ascii: bool = False) -> bytes:
    """Encode un DataFrame en JSON (bytes)."""
    return df.to_json(orient=orient, force_ascii=force_ascii).encode("utf-8")


def _safe_sheet_name(name: str) -> str:
    """
    Assainit un nom de feuille Excel : <=31 chars, sans []:*?/\\ et pas vide.
    """
    base = re.sub(r'[:\\/*?\[\]]', "-", (name or "Sheet"))
    base = base.strip() or "Sheet"
    return base[:31]


def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """
    Crée un classeur Excel en mémoire avec une feuille par entrée du dict.
    `sheets` : {'Matches': df1, 'Quarters': df2, ...}
    - Assainit les noms de feuilles et gère les doublons éventuels.
    - Ajuste grossièrement la largeur des colonnes et fige l’en-tête.
    """
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        used_names: set[str] = set()
        for raw_name, df in sheets.items():
            safe = _safe_sheet_name(str(raw_name) if raw_name else "Sheet")
            n = 1
            name = safe
            while name in used_names:
                suffix = f"_{n}"
                name = (safe[: (31 - len(suffix))] + suffix)
                n += 1
            used_names.add(name)

            sheet_df = (df or pd.DataFrame()).copy()
            # Petites normalisations utiles avant export
            if "Date" in sheet_df.columns:
                try:
                    sheet_df["Date"] = sheet_df["Date"].map(_to_date_str)
                except Exception:
                    pass

            sheet_df.to_excel(writer, sheet_name=name, index=False)

            # Mise en forme basique si xlsxwriter
            try:
                ws = writer.sheets[name]
                # Freeze header
                ws.freeze_panes(1, 0)
                # Auto-width (approx): largeur = max( min(40, max(len(str)) + 2) )
                for idx, col in enumerate(sheet_df.columns):
                    series = sheet_df[col].astype(str)
                    max_len = max([len(col)] + series.map(len).tolist()) if not series.empty else len(col)
                    ws.set_column(idx, idx, min(40, max_len + 2))
            except Exception:
                pass

    bio.seek(0)
    return bio.getvalue()


# ============================================================
# Bundles d’export
# ============================================================

def build_match_detail_dataframes(detail: Dict[str, Any], team_label: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    À partir d’un `detail` (dict retourné par get_match), produit les DataFrames :
    - 'Match' (1 ligne)
    - 'Quarters'
    - 'Players'
    """
    # Feuille Match (1 ligne)
    match_df = df_from_matches([detail])

    # Feuille Quarters
    home = (detail.get("home_club") or "Home")
    away = (detail.get("away_club") or "Away")
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


def export_match_bundle_excel(detail: Dict[str, Any], team_label: Optional[str] = None) -> Tuple[bytes, str]:
    """
    Construit un fichier Excel (bytes) pour un match : onglets Match / Quarters / Players.
    Retourne (bytes, suggested_filename).
    """
    dfs = build_match_detail_dataframes(detail, team_label=team_label)
    data = to_excel_bytes(dfs)
    mid = detail.get("id", "match")
    fname = f"match_{mid}.xlsx"
    return data, fname


def export_matches_overview_excel(rows: Iterable[Any], *, filename: str = "matches_overview.xlsx") -> Tuple[bytes, str]:
    """
    Construit un Excel (bytes) avec un onglet 'Matches' listant tous les matches.
    Retourne (bytes, suggested_filename).
    """
    df = build_matches_overview_dataframe(rows)
    data = to_excel_bytes({"Matches": df})
    return data, filename
# ---------------------------------------------------------------------------