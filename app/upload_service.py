from __future__ import annotations

import gc
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from processa_base_consolidada import consolidar_meta_vendido, enriquecer_com_supervisor
from processa_meta import consolidar_metas
from processa_vendido import consolidar_vendidos

from .data import BASE_DIR, DATA_FILE, META_DIR, SUPERVISOR_FILE, VENDIDO_DIR, clear_data_cache, get_base_status


META_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
VENDIDO_EXTENSIONS = {".txt"}
SUPERVISOR_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}


def _clean_filename(filename: str | None, fallback: str) -> str:
    clean_name = Path(filename or fallback).name.strip()
    return clean_name or fallback


def _assert_group(files: list[UploadFile], allowed_extensions: set[str], label: str) -> None:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Envie arquivos de {label}.")

    seen: set[str] = set()
    for upload in files:
        filename = _clean_filename(upload.filename, f"{label}.bin")
        suffix = Path(filename).suffix.lower()
        if suffix not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Arquivo invalido em {label}: {filename}",
            )
        lower_name = filename.lower()
        if lower_name in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Arquivo duplicado em {label}: {filename}",
            )
        seen.add(lower_name)


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = await upload.read()
    destination.write_bytes(content)
    await upload.close()


def _unlink_with_retry(path: Path, attempts: int = 10, base_delay: float = 0.5) -> None:
    """Tenta deletar um arquivo com retries para lidar com locks do Windows."""
    gc.collect()
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * (attempt + 1))


def _copy_with_retry(src: Path, dst: Path, attempts: int = 10, base_delay: float = 0.5) -> None:
    """Copia um arquivo com retries â€” overwrite seguro no Windows."""
    gc.collect()
    for attempt in range(attempts):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * (attempt + 1))


def _sort_final_base(final_df):
    if final_df.empty:
        return final_df

    ordering = [column for column in ("fornecedor", "mes", "cod_rca") if column in final_df.columns]
    if ordering:
        return final_df.sort_values(ordering, kind="stable").reset_index(drop=True)
    return final_df


def _apply_staged_files(
    temp_meta_dir: Path,
    temp_vendido_dir: Path,
    temp_supervisor_file: Path,
    temp_base_file: Path,
    temp_meta_consolidada: Path,
    temp_vendido_consolidado: Path,
) -> None:
    # LÃª rollback em memÃ³ria antes de qualquer modificaÃ§Ã£o
    rollback: dict[Path, bytes] = {}
    for pattern in ("*.xls", "*.xlsx", "*.xlsm"):
        for p in META_DIR.glob(pattern):
            if p.is_file():
                rollback[p] = p.read_bytes()
    for pattern in ("*.txt", "*.xlsx"):
        for p in VENDIDO_DIR.glob(pattern):
            if p.is_file():
                rollback[p] = p.read_bytes()
    if SUPERVISOR_FILE.exists():
        rollback[SUPERVISOR_FILE] = SUPERVISOR_FILE.read_bytes()
    if DATA_FILE.exists():
        rollback[DATA_FILE] = DATA_FILE.read_bytes()

    gc.collect()

    try:
        # 1. Overwrite / adiciona novos arquivos (nÃ£o deleta nada ainda)
        new_meta_names: set[str] = set()
        for file_path in temp_meta_dir.iterdir():
            if file_path.is_file():
                _copy_with_retry(file_path, META_DIR / file_path.name)
                new_meta_names.add(file_path.name.lower())

        new_vendido_names: set[str] = set()
        for file_path in temp_vendido_dir.iterdir():
            if file_path.is_file():
                _copy_with_retry(file_path, VENDIDO_DIR / file_path.name)
                new_vendido_names.add(file_path.name.lower())

        _copy_with_retry(temp_supervisor_file, SUPERVISOR_FILE)
        _copy_with_retry(temp_base_file, DATA_FILE)
        _copy_with_retry(temp_meta_consolidada, META_DIR / temp_meta_consolidada.name)
        _copy_with_retry(temp_vendido_consolidado, VENDIDO_DIR / temp_vendido_consolidado.name)

        # 2. Remove arquivos da rodada anterior que nÃ£o vieram no novo upload
        new_meta_names.add(temp_meta_consolidada.name.lower())
        new_vendido_names.add(temp_vendido_consolidado.name.lower())

        for pattern in ("*.xls", "*.xlsx", "*.xlsm"):
            for p in META_DIR.glob(pattern):
                if p.is_file() and p.name.lower() not in new_meta_names:
                    _unlink_with_retry(p)

        for pattern in ("*.txt",):
            for p in VENDIDO_DIR.glob(pattern):
                if p.is_file() and p.name.lower() not in new_vendido_names:
                    _unlink_with_retry(p)

    except Exception:
        # Restaura a partir do snapshot em memÃ³ria
        for path, data in rollback.items():
            try:
                path.write_bytes(data)
            except OSError:
                pass
        raise


async def replace_base_from_uploads(
    meta_files: list[UploadFile],
    vendido_files: list[UploadFile],
    supervisor_file: UploadFile,
) -> dict:
    _assert_group(meta_files, META_EXTENSIONS, "Meta")
    _assert_group(vendido_files, VENDIDO_EXTENSIONS, "Vendido")
    _assert_group([supervisor_file], SUPERVISOR_EXTENSIONS, "Supervisor")

    with tempfile.TemporaryDirectory(dir=BASE_DIR) as temp_root_str:
        temp_root = Path(temp_root_str)
        temp_meta_dir = temp_root / "Meta"
        temp_vendido_dir = temp_root / "Vendido"
        temp_supervisor_file = temp_root / _clean_filename(supervisor_file.filename, "Supervisor_RCA.xlsx")
        temp_meta_consolidada = temp_root / "meta_consolidada.xlsx"
        temp_vendido_consolidado = temp_root / "vendido_consolidado.xlsx"
        temp_base_file = temp_root / "base_consolidada.xlsx"

        for upload in meta_files:
            destination = temp_meta_dir / _clean_filename(upload.filename, "meta.xlsx")
            await _save_upload(upload, destination)

        for upload in vendido_files:
            destination = temp_vendido_dir / _clean_filename(upload.filename, "vendido.txt")
            await _save_upload(upload, destination)

        await _save_upload(supervisor_file, temp_supervisor_file)

        try:
            consolidar_metas(temp_meta_dir, salvar_em=temp_meta_consolidada)
            consolidar_vendidos(temp_vendido_dir, salvar_em=temp_vendido_consolidado)
            base_df = consolidar_meta_vendido(temp_meta_dir, temp_vendido_dir)
            final_df = enriquecer_com_supervisor(base_df, temp_supervisor_file)
            final_df = _sort_final_base(final_df)
            final_df.to_excel(temp_base_file, index=False)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nao foi possivel processar os arquivos enviados: {exc}",
            ) from exc

        _apply_staged_files(
            temp_meta_dir=temp_meta_dir,
            temp_vendido_dir=temp_vendido_dir,
            temp_supervisor_file=temp_supervisor_file,
            temp_base_file=temp_base_file,
            temp_meta_consolidada=temp_meta_consolidada,
            temp_vendido_consolidado=temp_vendido_consolidado,
        )

    clear_data_cache()

    status_payload = get_base_status()
    status_payload.update(
        {
            "status": "success",
            "message": "Base atualizada com sucesso.",
            "meta_uploaded": len(meta_files),
            "vendido_uploaded": len(vendido_files),
            "rows_generated": status_payload["row_count"],
        }
    )
    return status_payload
