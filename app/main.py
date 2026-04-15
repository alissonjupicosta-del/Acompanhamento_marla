from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .data import get_base_status, get_filter_options, get_fornecedores_payload, get_overview_payload, get_supervisores_payload, get_vendedores_payload
from .upload_service import replace_base_from_uploads


APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(
    title="Dashboard Comercial",
    description="Painel comercial com analises segmentadas e atualizacao da base via upload.",
    version="2.0.0",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

NAV_ITEMS = [
    {"key": "overview", "label": "Visao Geral", "href": "/"},
    {"key": "vendedores", "label": "Vendedores", "href": "/vendedores"},
    {"key": "fornecedores", "label": "Fornecedores", "href": "/fornecedores"},
    {"key": "supervisores", "label": "Supervisores", "href": "/supervisores"},
    {"key": "upload", "label": "Atualizar Base", "href": "/atualizar-base"},
]


def _template_context(request: Request, page_key: str, title: str, filters_enabled: bool) -> dict:
    return {
        "request": request,
        "page_key": page_key,
        "page_title": title,
        "filters_enabled": filters_enabled,
        "nav_items": NAV_ITEMS,
        "base_status": get_base_status(),
    }


def _dashboard_response(request: Request, page_key: str, title: str, filters_enabled: bool) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=_template_context(request, page_key, title, filters_enabled),
    )


@app.get("/", response_class=HTMLResponse)
async def overview_page(request: Request) -> HTMLResponse:
    return _dashboard_response(request, "overview", "Visao Geral", True)


@app.get("/vendedores", response_class=HTMLResponse)
async def vendedores_page(request: Request) -> HTMLResponse:
    return _dashboard_response(request, "vendedores", "Vendedores", True)


@app.get("/fornecedores", response_class=HTMLResponse)
async def fornecedores_page(request: Request) -> HTMLResponse:
    return _dashboard_response(request, "fornecedores", "Fornecedores", True)


@app.get("/supervisores", response_class=HTMLResponse)
async def supervisores_page(request: Request) -> HTMLResponse:
    return _dashboard_response(request, "supervisores", "Supervisores", True)


@app.get("/atualizar-base", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    return _dashboard_response(request, "upload", "Atualizar Base", False)


@app.get("/api/filters")
async def filters() -> dict:
    return get_filter_options()


@app.get("/api/overview")
async def overview_data(
    vendedor: Annotated[list[str] | None, Query()] = None,
    fornecedor: Annotated[list[str] | None, Query()] = None,
    supervisor: Annotated[list[str] | None, Query()] = None,
) -> dict:
    return get_overview_payload(vendedor, fornecedor, supervisor)


@app.get("/api/vendedores")
async def vendedores_data(
    vendedor: Annotated[list[str] | None, Query()] = None,
    fornecedor: Annotated[list[str] | None, Query()] = None,
    supervisor: Annotated[list[str] | None, Query()] = None,
) -> dict:
    return get_vendedores_payload(vendedor, fornecedor, supervisor)


@app.get("/api/fornecedores")
async def fornecedores_data(
    vendedor: Annotated[list[str] | None, Query()] = None,
    fornecedor: Annotated[list[str] | None, Query()] = None,
    supervisor: Annotated[list[str] | None, Query()] = None,
) -> dict:
    return get_fornecedores_payload(vendedor, fornecedor, supervisor)


@app.get("/api/supervisores")
async def supervisores_data(
    vendedor: Annotated[list[str] | None, Query()] = None,
    fornecedor: Annotated[list[str] | None, Query()] = None,
    supervisor: Annotated[list[str] | None, Query()] = None,
) -> dict:
    return get_supervisores_payload(vendedor, fornecedor, supervisor)


@app.post("/api/base/upload")
async def upload_base(
    meta_files: Annotated[list[UploadFile], File(...)],
    vendido_files: Annotated[list[UploadFile], File(...)],
    supervisor_file: Annotated[UploadFile, File(...)],
) -> dict:
    return await replace_base_from_uploads(meta_files, vendido_files, supervisor_file)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
