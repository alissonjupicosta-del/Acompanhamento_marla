from __future__ import annotations

from pathlib import Path

import pandas as pd

from processa_meta import consolidar_metas
from processa_vendido import consolidar_vendidos


def consolidar_meta_vendido(
    pasta_meta: str | Path = "Meta",
    pasta_vendido: str | Path = "Vendido",
    salvar_em: str | Path | None = None,
    how: str = "outer",
) -> pd.DataFrame:
    """
    Junta as bases de Meta e Vendido pela chave `fornecedor` + `cod_rca`.

    Parameters
    ----------
    pasta_meta:
        Pasta com os arquivos de meta.
    pasta_vendido:
        Pasta com os arquivos de vendido.
    salvar_em:
        Se informado, salva o consolidado em .xlsx ou .csv.
    how:
        Tipo de merge do pandas. O padrao e `outer` para nao perder registros.
    """
    df_meta = consolidar_metas(pasta_meta=pasta_meta)
    df_vendido = consolidar_vendidos(pasta_vendido=pasta_vendido)

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
    """
    Acrescenta as colunas de supervisor e vendedor usando a chave `cod_rca`.

    A planilha de supervisores usa `RCA` como nome da chave, entÃ£o fazemos a
    padronizacao antes do merge para manter o fluxo simples e previsivel.
    """
    if base.empty:
        return base.copy()

    caminho_supervisor = Path(arquivo_supervisor)
    if not caminho_supervisor.exists():
        return base.copy()

    df_supervisor = pd.read_excel(caminho_supervisor)
    if df_supervisor.empty:
        return base.copy()

    colunas_necessarias = {"RCA", "SUPERVISOR", "VENDEDOR"}
    if not colunas_necessarias.issubset(df_supervisor.columns):
        return base.copy()

    df_supervisor = df_supervisor.rename(
        columns={
            "RCA": "cod_rca",
            "SUPERVISOR": "supervisor",
            "VENDEDOR": "vendedor",
        }
    )
    df_supervisor["cod_rca"] = pd.to_numeric(df_supervisor["cod_rca"], errors="coerce").astype("Int64")
    df_supervisor = df_supervisor.dropna(subset=["cod_rca"]).drop_duplicates(subset=["cod_rca"], keep="first")

    enriquecida = base.merge(
        df_supervisor[["cod_rca", "supervisor", "vendedor"]],
        on="cod_rca",
        how="left",
    )

    colunas = list(enriquecida.columns)
    for coluna in ("supervisor", "vendedor"):
        if coluna in colunas:
            colunas.remove(coluna)

    if "cod_rca" in colunas:
        posicao = colunas.index("cod_rca") + 1
        colunas = colunas[:posicao] + ["supervisor", "vendedor"] + colunas[posicao:]

    enriquecida = enriquecida[colunas]
    return enriquecida


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
