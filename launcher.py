"""Ponto de entrada do executavel gerado pelo PyInstaller.

Em ambiente desktop, inicia o servidor FastAPI em background e abre a
interface local. Em ambiente de deploy, principalmente no Render, roda em
modo headless e sobe apenas o servidor web.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import time

DESKTOP_HOST = "127.0.0.1"
PORT = int(os.getenv("PORT", "8000"))
SERVER_HOST = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else DESKTOP_HOST)
URL = f"http://{DESKTOP_HOST}:{PORT}"


def _start_server() -> None:
    import uvicorn
    from app.main import app as fastapi_app

    uvicorn.run(fastapi_app, host=SERVER_HOST, port=PORT, log_level="error")


def _open_browser_after_delay(delay: float = 2.0) -> None:
    import webbrowser

    time.sleep(delay)
    webbrowser.open(URL)


def _build_window():
    import tkinter as tk

    root = tk.Tk()
    root.title("Dashboard Comercial")
    root.geometry("340x170")
    root.resizable(False, False)
    root.configure(bg="#f5f5f5")

    tk.Label(
        root,
        text="Servidor rodando em:",
        font=("Segoe UI", 10),
        bg="#f5f5f5",
        fg="#333333",
    ).pack(pady=(22, 2))

    tk.Label(
        root,
        text=URL,
        font=("Segoe UI", 10, "bold"),
        bg="#f5f5f5",
        fg="#0066cc",
        cursor="hand2",
    ).pack()

    btn_frame = tk.Frame(root, bg="#f5f5f5")
    btn_frame.pack(pady=18)

    tk.Button(
        btn_frame,
        text="Abrir no Navegador",
        command=lambda: __import__("webbrowser").open(URL),
        width=22,
        font=("Segoe UI", 9),
        bg="#0066cc",
        fg="white",
        relief="flat",
        cursor="hand2",
    ).grid(row=0, column=0, padx=6)

    tk.Button(
        btn_frame,
        text="Encerrar Servidor",
        command=root.destroy,
        width=18,
        font=("Segoe UI", 9),
        bg="#cc2200",
        fg="white",
        relief="flat",
        cursor="hand2",
    ).grid(row=0, column=1, padx=6)

    return root


def main() -> None:
    multiprocessing.freeze_support()

    if os.getenv("PORT"):
        _start_server()
        return

    try:
        server_thread = threading.Thread(target=_start_server, daemon=True)
        server_thread.start()

        browser_thread = threading.Thread(target=_open_browser_after_delay, daemon=True)
        browser_thread.start()

        root = _build_window()
        root.mainloop()

    except Exception as exc:  # noqa: BLE001
        try:
            import tkinter.messagebox as mb

            mb.showerror("Erro ao iniciar", str(exc))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
