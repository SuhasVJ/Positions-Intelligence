import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.kite_service import KiteService

load_dotenv()
IST = ZoneInfo("Asia/Kolkata")
kite = KiteService()
refresh_seconds = max(2, int(os.getenv("POSITION_REFRESH_SECONDS", "5")))
clients: set[WebSocket] = set()


class SessionRequest(BaseModel):
    request_token: str


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
                message = {"type": "error", "message": str(exc)}
                for client in list(clients):
                    with suppress(Exception):
                        await client.send_json(message)
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
    version="0.1.0",
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


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse("app/static/index.html")


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


@app.post("/api/auth/session")
async def auth_session(request: SessionRequest):
    try:
        user = await run_in_threadpool(kite.create_session, request.request_token)
        return {"authenticated": True, "user": user}
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


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
                "message": "Kite session is not authenticated. Complete the Kite login flow first.",
            })
        while True:
            # Keep the connection alive; snapshots are pushed by the broadcaster.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)
