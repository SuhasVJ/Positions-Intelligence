import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.kite_service import KiteService

load_dotenv()
IST = ZoneInfo("Asia/Kolkata")
kite = KiteService()
refresh_seconds = max(2, int(os.getenv("POSITION_REFRESH_SECONDS", "5")))
clients: set[WebSocket] = set()


def make_snapshot() -> dict[str, Any]:
    positions = kite.get_day_positions()
    return {
        "as_of": datetime.now(IST).isoformat(),
        "positions": positions,
        "summary": kite.summarize(positions),
    }


async def publish_positions() -> None:
    while True:
        if clients and kite.authenticated:
            try:
                snapshot = await run_in_threadpool(make_snapshot)
                stale_clients = []
                for client in list(clients):
                    try:
                        await client.send_json({"type": "positions", "data": snapshot})
                    except Exception:
                        stale_clients.append(client)
                for client in stale_clients:
                    clients.discard(client)
            except Exception as exc:
                for client in list(clients):
                    with suppress(Exception):
                        await client.send_json({"type": "error", "message": str(exc)})
        await asyncio.sleep(refresh_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(publish_positions())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Positions Intelligence API",
    description="Read-only today's positions from Zerodha Kite Connect.",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


async def complete_kite_login(request_token: str | None, status: str | None):
    if status == "cancel":
        return RedirectResponse(url="/?login=cancelled", status_code=303)
    if status != "success" or not request_token:
        return RedirectResponse(url="/?login=failed", status_code=303)
    try:
        # Exchange the short-lived request token immediately; never persist or log it.
        await run_in_threadpool(kite.create_session, request_token)
    except Exception:
        return RedirectResponse(url="/?login=failed", status_code=303)
    # Strip the request token and all Kite query parameters from the browser URL.
    return RedirectResponse(url="/api/positions/intelligence", status_code=303)


@app.get("/", include_in_schema=False)
async def login_page(
    request_token: str | None = None,
    status: str | None = None,
    action: str | None = None,
):
    # Kite commonly redirects to the configured root URL with OAuth query parameters.
    if request_token or action == "login":
        return await complete_kite_login(request_token, status)
    if kite.authenticated:
        return RedirectResponse(url="/api/positions/intelligence", status_code=303)
    return FileResponse("app/static/index.html")


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request_token: str | None = None, status: str | None = None):
    return await complete_kite_login(request_token, status)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "kite_configured": bool(kite.api_key),
        "authenticated": kite.authenticated,
        "refresh_seconds": refresh_seconds,
    }


@app.get("/api/auth/login")
async def auth_login():
    try:
        return {"login_url": kite.login_url()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/logout", include_in_schema=False)
async def logout():
    kite.clear_session()
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/positions/intelligence", include_in_schema=False)
async def positions_intelligence():
    if not kite.authenticated:
        return RedirectResponse(url="/", status_code=303)
    return FileResponse("app/static/positions.html")


@app.get("/api/positions/today")
async def today_positions():
    if not kite.authenticated:
        raise HTTPException(
            status_code=401,
            detail="Kite session is not authenticated. Complete the Kite login flow first.",
        )
    try:
        return await run_in_threadpool(make_snapshot)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}") from exc


@app.websocket("/ws/positions")
async def positions_socket(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        if kite.authenticated:
            snapshot = await run_in_threadpool(make_snapshot)
            await websocket.send_json({"type": "positions", "data": snapshot})
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Kite session is not authenticated. Please log in again.",
            })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)
