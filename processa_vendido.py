from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


DEFAULT_COLUNAS = [
    "Codigo",
    "Nome",
    "Qt.Cli.Ativos",
    "Qt.Cli.Pos.",
    "% Pos.",
    "Qt. Vendida",
    "Vl.Vendido",
    "%",
    "Peso (Kg)",
    "Volume",
]

COD_RCA_ALIASES = ("cod_rca", "codigo", "cod", "rca", "ca3digo")


def _normalizar_nome_coluna(nome: object) -> str:
    texto = str(nome).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = texto.replace("%", " pct ")
    texto = texto.replace(".", " ")
    texto = texto.replace("/", " ")
    texto = texto.replace("-", " ")
    texto = texto.replace("(", " ")
    texto = texto.replace(")", " ")
    return "_".join(texto.split())


def _converter_numero_br(valor: object) -> object:
    if pd.isna(valor):
        return pd.NA

    texto = str(valor).strip()
    if not texto:
        return pd.NA

    texto = texto.replace("Kg", "").replace("kg", "").strip()
    texto = re.sub(r"[^0-9,\.\-]", "", texto)

    if not texto:
        return pd.NA

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return pd.NA


def _padronizar_coluna_cod_rca(df: pd.DataFrame, origem: Path) -> pd.DataFrame:
    for alias in COD_RCA_ALIASES:
        if alias in df.columns:
            return df.rename(columns={alias: "cod_rca"})

    raise ValueError(
        "Nao foi possivel identificar a coluna do codigo RCA no arquivo "
        f"{origem.name}. Colunas encontradas: {', '.join(map(str, df.columns))}"
    )


def _ler_arquivo_vendido(caminho_arquivo: Path, cabecalho: list[str]) -> pd.DataFrame:
    tentativas = ("utf-8", "latin-1")
    ultimo_erro: Exception | None = None

    for encoding in tentativas:
        try:
            df = pd.read_csv(
                caminho_arquivo,
                header=None,
                names=cabecalho,
                sep=",",
                quotechar='"',
                dtype=str,
                encoding=encoding,
                engine="python",
            )
            break
        except Exception as erro:
            ultimo_erro = erro
    else:
        raise ultimo_erro  # type: ignore[misc]

    df = df.dropna(how="all").copy()
    df.columns = [_normalizar_nome_coluna(coluna) for coluna in df.columns]
    df = _padronizar_coluna_cod_rca(df, caminho_arquivo)

    if "nome" in df.columns:
        df["nome"] = df["nome"].astype("string").str.strip()

    df["cod_rca"] = pd.to_numeric(df["cod_rca"], errors="coerce").astype("Int64")

    for coluna in df.columns:
        if coluna not in {"cod_rca", "nome", "fornecedor", "arquivo_origem"}:
            df[coluna] = df[coluna].map(_converter_numero_br)

    df["fornecedor"] = caminho_arquivo.stem.replace("-", "").strip()
    df["arquivo_origem"] = caminho_arquivo.name

    return df


def consolidar_vendidos(
    pasta_vendido: str | Path = "Vendido",
    salvar_em: str | Path | None = None,
    cabecalho: list[str] | None = None,
) -> pd.DataFrame:
    pasta_vendido = Path(pasta_vendido)
    arquivos = sorted(pasta_vendido.glob("*.txt"))
    cabecalho = cabecalho or DEFAULT_COLUNAS

    if not arquivos:
        consolidado = pd.DataFrame(columns=[_normalizar_nome_coluna(c) for c in cabecalho])
    else:
        frames = [_ler_arquivo_vendido(arquivo, cabecalho) for arquivo in arquivos]
        consolidado = pd.concat(frames, ignore_index=True)

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


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    pasta_vendido = base_dir / "Vendido"
    destino = pasta_vendido / "vendido_consolidado.xlsx"

    df = consolidar_vendidos(pasta_vendido=pasta_vendido, salvar_em=destino)
    print(f"Vendido consolidado gerado em: {destino}")
    print(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")


if __name__ == "__main__":
    main()
