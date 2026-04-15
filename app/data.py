from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


import sys as _sys
BASE_DIR = Path(_sys.executable).parent if getattr(_sys, "frozen", False) else Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "base_consolidada.xlsx"
META_DIR = BASE_DIR / "Meta"
VENDIDO_DIR = BASE_DIR / "Vendido"
SUPERVISOR_FILE = BASE_DIR / "Supervisor_RCA.xlsx"

TEXT_COLUMNS = ("supervisor", "vendedor", "fornecedor", "nome", "origem_merge")
NUMERIC_COLUMNS = (
    "vl_venda",
    "cli_pos",
    "qt_cli_ativos",
    "qt_cli_pos",
    "pct_pos",
    "qt_vendida",
    "vl_vendido",
    "pct",
    "peso_kg",
    "volume",
)
MONTH_NAMES_PT = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def _safe_pct(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _clean_text(series: pd.Series, fallback: str = "Nao informado") -> pd.Series:
    cleaned = series.astype("string").fillna(fallback).str.strip()
    return cleaned.replace("", fallback)


def _format_month(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "Sem mes"
    return f"{MONTH_NAMES_PT[int(timestamp.month)]}/{int(timestamp.year)}"


def _current_data_version() -> int:
    if not DATA_FILE.exists():
        return 0
    return DATA_FILE.stat().st_mtime_ns


@lru_cache(maxsize=2)
def _load_sales_data_cached(version: int) -> pd.DataFrame:
    del version

    if not DATA_FILE.exists():
        return pd.DataFrame()

    df = pd.read_excel(DATA_FILE)
    if df.empty:
        return df

    for column in TEXT_COLUMNS:
        if column in df.columns:
            df[column] = _clean_text(df[column])

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    if "cod_rca" in df.columns:
        df["cod_rca"] = pd.to_numeric(df["cod_rca"], errors="coerce").astype("Int64")

    if "mes" in df.columns:
        df["mes"] = pd.to_datetime(df["mes"], errors="coerce")
        df["mes_label"] = df["mes"].map(_format_month)
    else:
        df["mes_label"] = "Sem mes"

    df["atingimento_item"] = [
        _safe_pct(float(vendido), float(meta))
        for vendido, meta in zip(df["vl_vendido"], df["vl_venda"], strict=False)
    ]
    df["positivacao_item"] = [
        _safe_pct(float(realizado), float(meta))
        for realizado, meta in zip(df["qt_cli_pos"], df["cli_pos"], strict=False)
    ]

    return df


def clear_data_cache() -> None:
    _load_sales_data_cached.cache_clear()


def load_sales_data() -> pd.DataFrame:
    return _load_sales_data_cached(_current_data_version()).copy()


def data_last_updated() -> str:
    if not DATA_FILE.exists():
        return "Base nao encontrada"
    return datetime.fromtimestamp(DATA_FILE.stat().st_mtime).strftime("%d/%m/%Y %H:%M")


def _source_file_count(directory: Path, patterns: tuple[str, ...], ignored_prefixes: tuple[str, ...] = ()) -> int:
    files = [
        path
        for pattern in patterns
        for path in directory.glob(pattern)
        if path.is_file() and not path.name.lower().startswith(ignored_prefixes)
    ]
    return len(files)


def get_base_status() -> dict[str, Any]:
    df = load_sales_data()
    months = sorted(df["mes_label"].dropna().unique().tolist()) if not df.empty else []
    return {
        "updated_at": data_last_updated(),
        "row_count": int(len(df)),
        "months": months,
        "meta_files": _source_file_count(META_DIR, ("*.xls", "*.xlsx", "*.xlsm"), ("meta_consolidada", "~$")),
        "vendido_files": _source_file_count(VENDIDO_DIR, ("*.txt",), ("~$",)),
        "has_supervisor": SUPERVISOR_FILE.exists(),
    }


def get_filter_options() -> dict[str, Any]:
    df = load_sales_data()

    if df.empty:
        return {
            "vendedores": [],
            "fornecedores": [],
            "supervisores": [],
            "meses": [],
            "updated_at": data_last_updated(),
        }

    return {
        "vendedores": sorted(df["vendedor"].dropna().unique().tolist()),
        "fornecedores": sorted(df["fornecedor"].dropna().unique().tolist()),
        "supervisores": sorted(df["supervisor"].dropna().unique().tolist()),
        "meses": sorted(df["mes_label"].dropna().unique().tolist()),
        "updated_at": data_last_updated(),
    }


def apply_filters(
    df: pd.DataFrame,
    vendedores: list[str] | None = None,
    fornecedores: list[str] | None = None,
    supervisores: list[str] | None = None,
) -> pd.DataFrame:
    filtered = df.copy()

    if vendedores:
        filtered = filtered[filtered["vendedor"].isin(vendedores)]
    if fornecedores:
        filtered = filtered[filtered["fornecedor"].isin(fornecedores)]
    if supervisores:
        filtered = filtered[filtered["supervisor"].isin(supervisores)]

    return filtered.reset_index(drop=True)


def _build_metadata(
    filtered: pd.DataFrame,
    vendedores: list[str] | None,
    fornecedores: list[str] | None,
    supervisores: list[str] | None,
) -> dict[str, Any]:
    return {
        "updated_at": data_last_updated(),
        "rows": int(len(filtered)),
        "meses": sorted(filtered["mes_label"].dropna().unique().tolist()) if not filtered.empty else [],
        "active_filters": {
            "vendedores": vendedores or [],
            "fornecedores": fornecedores or [],
            "supervisores": supervisores or [],
        },
    }


def _sum(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return float(df[column].sum())


def _format_positivacao_detail(meta_total: float, real_total: float) -> str:
    return f"{int(round(real_total))}/{int(round(meta_total))}"


def _build_kpis(df: pd.DataFrame, specs: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    totals = {
        "vendido": _sum(df, "vl_vendido"),
        "meta": _sum(df, "vl_venda"),
        "positivado_meta": _sum(df, "cli_pos"),
        "positivado_real": _sum(df, "qt_cli_pos"),
        "volume": _sum(df, "volume"),
        "fornecedores": float(df["fornecedor"].nunique()) if "fornecedor" in df.columns else 0.0,
        "supervisores": float(df["supervisor"].nunique()) if "supervisor" in df.columns else 0.0,
    }

    values = {
        "vendido": {
            "value": totals["vendido"],
            "kind": "currency",
            "detail": None,
            "icon": "sales",
        },
        "meta": {
            "value": totals["meta"],
            "kind": "currency",
            "detail": None,
            "icon": "target",
        },
        "atingimento": {
            "value": _safe_pct(totals["vendido"], totals["meta"]),
            "kind": "percent",
            "detail": None,
            "icon": "performance",
        },
        "positivado": {
            "value": _safe_pct(totals["positivado_real"], totals["positivado_meta"]),
            "kind": "percent",
            "detail": _format_positivacao_detail(totals["positivado_meta"], totals["positivado_real"]),
            "icon": "users",
        },
        "volume": {
            "value": totals["volume"],
            "kind": "number",
            "detail": None,
            "icon": "supplier",
        },
        "fornecedores": {
            "value": totals["fornecedores"],
            "kind": "number",
            "detail": None,
            "icon": "supplier",
        },
        "supervisores": {
            "value": totals["supervisores"],
            "kind": "number",
            "detail": None,
            "icon": "supervisor",
        },
    }

    return [
        {
            "label": label,
            "value": values[key]["value"],
            "kind": values[key]["kind"],
            "detail": values[key]["detail"],
            "icon": icon_name or values[key]["icon"],
        }
        for key, label, icon_name in specs
    ]


def _build_status_mix(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    bands = pd.cut(
        df["atingimento_item"],
        bins=[-0.01, 30, 80, 100, float("inf")],
        labels=["<30%", "30-80%", "80-100%", ">100%"],
    )
    grouped = bands.value_counts(sort=False).rename_axis("faixa").reset_index(name="quantidade")
    return grouped.to_dict(orient="records")


def _add_positivacao_columns(grouped: pd.DataFrame) -> pd.DataFrame:
    grouped["positivacao"] = [
        _safe_pct(float(realizado), float(meta))
        for realizado, meta in zip(grouped["positivado_real"], grouped["positivado_meta"], strict=False)
    ]
    return grouped


def _build_overview_table(df: pd.DataFrame) -> list[dict[str, Any]]:
    grouped = (
        df.groupby(["vendedor", "supervisor", "fornecedor"], as_index=False, dropna=False)
        .agg(
            meta=("vl_venda", "sum"),
            vendido=("vl_vendido", "sum"),
            positivado_meta=("cli_pos", "sum"),
            positivado_real=("qt_cli_pos", "sum"),
        )
        .sort_values(["vendedor", "fornecedor"], kind="stable")
        .reset_index(drop=True)
    )

    grouped["atingimento"] = [
        _safe_pct(float(vendido), float(meta))
        for vendido, meta in zip(grouped["vendido"], grouped["meta"], strict=False)
    ]
    grouped = _add_positivacao_columns(grouped)
    return grouped.to_dict(orient="records")


def _build_vendedores_detail(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["vendedor", "supervisor", "fornecedor"], as_index=False, dropna=False)
        .agg(
            meta=("vl_venda", "sum"),
            vendido=("vl_vendido", "sum"),
            positivado_meta=("cli_pos", "sum"),
            positivado_real=("qt_cli_pos", "sum"),
        )
        .sort_values(["vendido", "meta"], ascending=[False, False], kind="stable")
        .reset_index(drop=True)
    )

    grouped["atingimento"] = [
        _safe_pct(float(vendido), float(meta))
        for vendido, meta in zip(grouped["vendido"], grouped["meta"], strict=False)
    ]
    return _add_positivacao_columns(grouped)


def _build_fornecedores_detail(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("fornecedor", as_index=False, dropna=False)
        .agg(
            meta=("vl_venda", "sum"),
            vendido=("vl_vendido", "sum"),
            positivado_meta=("cli_pos", "sum"),
            positivado_real=("qt_cli_pos", "sum"),
            volume=("volume", "sum"),
        )
        .sort_values(["vendido", "meta"], ascending=[False, False], kind="stable")
        .reset_index(drop=True)
    )

    grouped["atingimento"] = [
        _safe_pct(float(vendido), float(meta))
        for vendido, meta in zip(grouped["vendido"], grouped["meta"], strict=False)
    ]
    return _add_positivacao_columns(grouped)


def _build_supervisores_detail(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["supervisor", "fornecedor"], as_index=False, dropna=False)
        .agg(
            meta=("vl_venda", "sum"),
            vendido=("vl_vendido", "sum"),
            positivado_meta=("cli_pos", "sum"),
            positivado_real=("qt_cli_pos", "sum"),
        )
        .sort_values(["supervisor", "vendido"], ascending=[True, False], kind="stable")
        .reset_index(drop=True)
    )

    grouped["atingimento"] = [
        _safe_pct(float(vendido), float(meta))
        for vendido, meta in zip(grouped["vendido"], grouped["meta"], strict=False)
    ]
    return _add_positivacao_columns(grouped)


def get_overview_payload(
    vendedores: list[str] | None = None,
    fornecedores: list[str] | None = None,
    supervisores: list[str] | None = None,
) -> dict[str, Any]:
    df = apply_filters(load_sales_data(), vendedores, fornecedores, supervisores)

    if df.empty:
        return {
            "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
            "kpis": [],
            "charts": {"supervisores": [], "status": []},
            "table": [],
        }

    supervisors_df = (
        df.groupby("supervisor", as_index=False, dropna=False)
        .agg(vendido=("vl_vendido", "sum"))
        .sort_values("vendido", ascending=False, kind="stable")
        .reset_index(drop=True)
    )
    sold_total = float(supervisors_df["vendido"].sum())
    supervisors_df["participacao"] = [
        _safe_pct(float(vendido), sold_total) for vendido in supervisors_df["vendido"]
    ]

    return {
        "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
        "kpis": _build_kpis(
            df,
            [
                ("vendido", "Vendido", "sales"),
                ("meta", "Meta", "target"),
                ("atingimento", "Atingimento", "performance"),
                ("positivado", "Positivado", "users"),
            ],
        ),
        "charts": {
            "supervisores": supervisors_df.to_dict(orient="records"),
            "status": _build_status_mix(df),
        },
        "table": _build_overview_table(df),
    }


def get_vendedores_payload(
    vendedores: list[str] | None = None,
    fornecedores: list[str] | None = None,
    supervisores: list[str] | None = None,
) -> dict[str, Any]:
    df = apply_filters(load_sales_data(), vendedores, fornecedores, supervisores)

    if df.empty:
        return {
            "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
            "kpis": [],
            "chart": [],
            "table": [],
        }

    chart_df = (
        df.groupby(["vendedor", "supervisor"], as_index=False, dropna=False)
        .agg(vendido=("vl_vendido", "sum"))
        .sort_values("vendido", ascending=False, kind="stable")
        .reset_index(drop=True)
    )

    detail_df = _build_vendedores_detail(df)

    return {
        "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
        "kpis": _build_kpis(
            df,
            [
                ("vendido", "Vendido", "sales"),
                ("meta", "Meta", "target"),
                ("positivado", "Positivado", "users"),
                ("fornecedores", "Fornecedores", "supplier"),
            ],
        ),
        "chart": chart_df.head(12).to_dict(orient="records"),
        "table": detail_df.to_dict(orient="records"),
    }


def get_fornecedores_payload(
    vendedores: list[str] | None = None,
    fornecedores: list[str] | None = None,
    supervisores: list[str] | None = None,
) -> dict[str, Any]:
    df = apply_filters(load_sales_data(), vendedores, fornecedores, supervisores)

    if df.empty:
        return {
            "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
            "kpis": [],
            "chart": [],
            "table": [],
        }

    detail_df = _build_fornecedores_detail(df)

    return {
        "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
        "kpis": _build_kpis(
            df,
            [
                ("vendido", "Vendido", "sales"),
                ("meta", "Meta", "target"),
                ("positivado", "Positivado", "users"),
                ("volume", "Volume", "supplier"),
            ],
        ),
        "chart": detail_df.head(12).to_dict(orient="records"),
        "table": detail_df.to_dict(orient="records"),
    }


def get_supervisores_payload(
    vendedores: list[str] | None = None,
    fornecedores: list[str] | None = None,
    supervisores: list[str] | None = None,
) -> dict[str, Any]:
    df = apply_filters(load_sales_data(), vendedores, fornecedores, supervisores)

    if df.empty:
        return {
            "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
            "kpis": [],
            "chart": [],
            "table": [],
        }

    chart_df = (
        df.groupby(["supervisor", "fornecedor"], as_index=False, dropna=False)
        .agg(vendido=("vl_vendido", "sum"))
        .sort_values("vendido", ascending=False, kind="stable")
        .reset_index(drop=True)
    )

    detail_df = _build_supervisores_detail(df)

    return {
        "metadata": _build_metadata(df, vendedores, fornecedores, supervisores),
        "kpis": _build_kpis(
            df,
            [
                ("meta", "Meta Total", "target"),
                ("vendido", "Vendido", "sales"),
                ("positivado", "Positivado", "users"),
                ("fornecedores", "Fornecedores", "supplier"),
            ],
        ),
        "chart": chart_df.head(16).to_dict(orient="records"),
        "table": detail_df.to_dict(orient="records"),
    }
