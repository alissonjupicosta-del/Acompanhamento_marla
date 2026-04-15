from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from processa_meta import consolidar_metas
from processa_vendido import consolidar_vendidos


COD_RCA_ALIASES = ("cod_rca", "codigo", "cod", "rca", "ca3digo")


def _normalizar_nome_coluna(nome: object) -> str:
    texto = str(nome).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = texto.replace(".", " ")
    texto = texto.replace("/", " ")
    texto = texto.replace("-", " ")
    texto = texto.replace("%", " pct ")
    texto = texto.replace("(", " ")
    texto = texto.replace(")", " ")
    return "_".join(texto.split())


def _garantir_coluna_cod_rca(df: pd.DataFrame, origem: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    ajustado = df.copy()
    renomeadas = {_normalizar_nome_coluna(coluna): coluna for coluna in ajustado.columns}

    for alias in COD_RCA_ALIASES:
        coluna_original = renomeadas.get(alias)
        if coluna_original is not None:
            if coluna_original != "cod_rca":
                ajustado = ajustado.rename(columns={coluna_original: "cod_rca"})
            break
    else:
        raise ValueError(
            f"Nao foi possivel identificar a coluna cod_rca na base de {origem}. "
            f"Colunas encontradas: {', '.join(map(str, ajustado.columns))}"
        )

    ajustado["cod_rca"] = pd.to_numeric(ajustado["cod_rca"], errors="coerce").astype("Int64")
    ajustado = ajustado.dropna(subset=["cod_rca"])
    return ajustado


def _normalizar_supervisor(df_supervisor: pd.DataFrame, origem: Path) -> pd.DataFrame:
    renomeadas = {_normalizar_nome_coluna(coluna): coluna for coluna in df_supervisor.columns}
    obrigatorias = {
        "rca": "cod_rca",
        "supervisor": "supervisor",
        "vendedor": "vendedor",
    }

    faltantes = [alias for alias in obrigatorias if alias not in renomeadas]
    if faltantes:
        raise ValueError(
            "A planilha de supervisor precisa conter as colunas RCA, SUPERVISOR e VENDEDOR. "
            f"Arquivo recebido: {origem.name}. Colunas encontradas: {', '.join(map(str, df_supervisor.columns))}"
        )

    ajustado = df_supervisor.rename(
        columns={renomeadas[alias]: destino for alias, destino in obrigatorias.items()}
    )
    ajustado["cod_rca"] = pd.to_numeric(ajustado["cod_rca"], errors="coerce").astype("Int64")
    ajustado["supervisor"] = ajustado["supervisor"].astype("string").fillna("").str.strip()
    ajustado["vendedor"] = ajustado["vendedor"].astype("string").fillna("").str.strip()
    ajustado = ajustado.dropna(subset=["cod_rca"]).drop_duplicates(subset=["cod_rca"], keep="first")
    return ajustado[["cod_rca", "supervisor", "vendedor"]]


def consolidar_meta_vendido(
    pasta_meta: str | Path = "Meta",
    pasta_vendido: str | Path = "Vendido",
    salvar_em: str | Path | None = None,
    how: str = "outer",
) -> pd.DataFrame:
    df_meta = _garantir_coluna_cod_rca(consolidar_metas(pasta_meta=pasta_meta), "meta")
    df_vendido = _garantir_coluna_cod_rca(consolidar_vendidos(pasta_vendido=pasta_vendido), "vendido")

    if df_meta.empty and df_vendido.empty:
        consolidado = pd.DataFrame()
    elif df_meta.empty:
        consolidado = df_vendido.copy()
    elif df_vendido.empty:
        consolidado = df_meta.copy()
    else:
        consolidado = pd.merge(
            df_meta,
            df_vendido,
            on=["fornecedor", "cod_rca"],
            how=how,
            suffixes=("_meta", "_vendido"),
            indicator=True,
        )
        consolidado = consolidado.rename(columns={"_merge": "origem_merge"})

    if not consolidado.empty:
        ordenacao = [col for col in ("fornecedor", "cod_rca") if col in consolidado.columns]
        if ordenacao:
            consolidado = consolidado.sort_values(ordenacao, kind="stable").reset_index(drop=True)

    if salvar_em is not None:
        destino = Path(salvar_em)
        destino.parent.mkdir(parents=True, exist_ok=True)

        if destino.suffix.lower() == ".csv":
            consolidado.to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
        else:
            consolidado.to_excel(destino, index=False)

    return consolidado


def enriquecer_com_supervisor(
    base: pd.DataFrame,
    arquivo_supervisor: str | Path = "Supervisor_RCA.xlsx",
) -> pd.DataFrame:
    if base.empty:
        return base.copy()

    caminho_supervisor = Path(arquivo_supervisor)
    if not caminho_supervisor.exists():
        return base.copy()

    df_supervisor = pd.read_excel(caminho_supervisor)
    if df_supervisor.empty:
        return base.copy()

    base = _garantir_coluna_cod_rca(base, "base consolidada")
    supervisor = _normalizar_supervisor(df_supervisor, caminho_supervisor)

    enriquecida = base.merge(supervisor, on="cod_rca", how="left")

    colunas = list(enriquecida.columns)
    for coluna in ("supervisor", "vendedor"):
        if coluna in colunas:
            colunas.remove(coluna)

    if "cod_rca" in colunas:
        posicao = colunas.index("cod_rca") + 1
        colunas = colunas[:posicao] + ["supervisor", "vendedor"] + colunas[posicao:]

    return enriquecida[colunas]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    destino_base = base_dir / "base_consolidada.xlsx"

    df_base = consolidar_meta_vendido(
        pasta_meta=base_dir / "Meta",
        pasta_vendido=base_dir / "Vendido",
        salvar_em=destino_base,
    )

    df_final = enriquecer_com_supervisor(df_base, arquivo_supervisor=base_dir / "Supervisor_RCA.xlsx")
    if not df_final.empty:
        ordenacao = [col for col in ("fornecedor", "mes", "cod_rca") if col in df_final.columns]
        if ordenacao:
            df_final = df_final.sort_values(ordenacao, kind="stable").reset_index(drop=True)

    df_final.to_excel(destino_base, index=False)

    print(f"Base consolidada gerada em: {destino_base}")
    print(f"Base consolidada sobrescrita com supervisor em: {destino_base}")
    print(f"Linhas: {len(df_final)} | Colunas: {len(df_final.columns)}")


if __name__ == "__main__":
    main()
