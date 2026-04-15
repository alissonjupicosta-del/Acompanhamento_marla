from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd


def _normalizar_nome_coluna(nome: object) -> str:
    """Converte nomes de colunas para um padrao simples e reutilizavel."""
    texto = str(nome).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = texto.replace(".", " ")
    texto = texto.replace("/", " ")
    texto = texto.replace("-", " ")
    texto = "_".join(texto.split())
    return texto


def _ler_planilha_meta(caminho_arquivo: Path) -> pd.DataFrame:
    """Le um arquivo de meta e devolve um DataFrame tratado."""
    frames: list[pd.DataFrame] = []

    with pd.ExcelFile(caminho_arquivo) as xls:
        sheet_names = xls.sheet_names
        raw_frames = {aba: pd.read_excel(xls, sheet_name=aba) for aba in sheet_names}

    for aba in sheet_names:
        df = raw_frames[aba]

        if df.empty:
            continue

        df = df.dropna(how="all").copy()
        df.columns = [_normalizar_nome_coluna(coluna) for coluna in df.columns]

        # Padroniza os campos esperados para facilitar o uso no backend/dashboards.
        if "mes" in df.columns:
            df["mes"] = pd.to_datetime(df["mes"], errors="coerce")

        for coluna in ("cod_rca", "dias_uteis", "vl_venda", "cli_pos"):
            if coluna in df.columns:
                df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

        if "cod_rca" in df.columns:
            df["cod_rca"] = df["cod_rca"].astype("Int64")
        if "dias_uteis" in df.columns:
            df["dias_uteis"] = df["dias_uteis"].astype("Int64")
        if "cli_pos" in df.columns:
            df["cli_pos"] = df["cli_pos"].astype("Int64")

        df["fornecedor"] = caminho_arquivo.stem
        df["arquivo_origem"] = caminho_arquivo.name
        df["aba_origem"] = aba

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def consolidar_metas(
    pasta_meta: str | Path = "Meta",
    salvar_em: str | Path | None = None,
) -> pd.DataFrame:
    """
    Le todos os arquivos de meta da pasta informada, trata os dados e concatena.

    Parameters
    ----------
    pasta_meta:
        Pasta onde estao os arquivos por fornecedor.
    salvar_em:
        Se informado, salva o consolidado em .xlsx ou .csv.

    Returns
    -------
    pd.DataFrame
        Base consolidada com colunas padronizadas.
    """
    pasta_meta = Path(pasta_meta)
    arquivos = sorted(
        [
            *pasta_meta.glob("*.xls"),
            *pasta_meta.glob("*.xlsx"),
            *pasta_meta.glob("*.xlsm"),
        ]
    )
    arquivos = [
        arquivo
        for arquivo in arquivos
        if not arquivo.name.lower().startswith(("meta_consolidada", "~$"))
    ]

    frames: list[pd.DataFrame] = []
    for arquivo in arquivos:
        frames.append(_ler_planilha_meta(arquivo))

    if not frames:
        consolidado = pd.DataFrame()
    else:
        consolidado = pd.concat(frames, ignore_index=True)

    if not consolidado.empty:
        ordenacao = [col for col in ("fornecedor", "mes", "cod_rca") if col in consolidado.columns]
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


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    pasta_meta = base_dir / "Meta"
    destino = pasta_meta / "meta_consolidada.xlsx"

    df = consolidar_metas(pasta_meta=pasta_meta, salvar_em=destino)
    print(f"Meta consolidada gerada em: {destino}")
    print(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")


if __name__ == "__main__":
    main()
