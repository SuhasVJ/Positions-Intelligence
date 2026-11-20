import asyncio
import os
import threading
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from kiteconnect import KiteTicker
from starlette.concurrency import run_in_threadpool

from app.kite_service import KiteService

load_dotenv()
IST = ZoneInfo("Asia/Kolkata")
kite = KiteService()
refresh_seconds = max(10, int(os.getenv("POSITION_REFRESH_SECONDS", "30")))
clients: set[WebSocket] = set()
snapshot_lock = threading.RLock()
latest_snapshot: dict[str, Any] | None = None
ticker: KiteTicker | None = None
subscribed_tokens: set[int] = set()
event_loop: asyncio.AbstractEventLoop | None = None


def make_snapshot() -> dict[str, Any]:
    positions = kite.get_positions()
    return {
        "as_of": datetime.now(IST).isoformat(),
        "price_feed": "KiteTicker" if ticker else "REST snapshot",
        "day": positions["day"],
        "net": positions["net"],
        "day_summary": kite.summarize(positions["day"]),
        "net_summary": kite.summarize(positions["net"]),
        "positions": positions["day"],
        "summary": kite.summarize(positions["day"]),
    }


def store_snapshot(data: dict[str, Any]) -> None:
    global latest_snapshot
    with snapshot_lock:
        latest_snapshot = data


def read_snapshot() -> dict[str, Any] | None:
    with snapshot_lock:
        return latest_snapshot


async def broadcast_snapshot() -> None:
    data = read_snapshot()
    if not data:
        return
    stale = []
    for client in list(clients):
        try:
            await client.send_json({"type": "positions", "data": data})
        except Exception:
            stale.append(client)
    for client in stale:
        clients.discard(client)


def on_ticker_ticks(_: KiteTicker, ticks: list[dict[str, Any]]) -> None:
    data = read_snapshot()
    if not data:
        return
    tick_prices = {int(t["instrument_token"]): float(t["last_price"]) for t in ticks
                   if t.get("instrument_token") and t.get("last_price") is not None}
    if not tick_prices:
        return
    with snapshot_lock:
        current = latest_snapshot
        if not current:
            return
        changed = False
        for collection in ("day", "net"):
            for position in current.get(collection, []):
                token = position.get("instrument_token")
                if token is None or int(token) not in tick_prices:
                    continue
                ltp = tick_prices[int(token)]
                quantity = int(position.get("quantity") or 0)
                previous_ltp = float(position.get("last_price") or 0)
                previous_unrealised = float(position.get("unrealised") or 0)
                position["last_price"] = ltp
                # Apply only the tick-to-tick mark-to-market change to Kite's REST baseline.
                position["unrealised"] = round(previous_unrealised + (ltp - previous_ltp) * quantity, 2)
                position["pnl"] = round(float(position.get("realised") or 0) + position["unrealised"], 2)
                changed = True
        if changed:
            current["net_summary"] = kite.summarize(current["net"])
            current["day_summary"] = kite.summarize(current["day"])
            current["as_of"] = datetime.now(IST).isoformat()
            current["price_feed"] = "KiteTicker"
            current["positions"] = current["day"]
            current["summary"] = current["day_summary"]
    if changed and event_loop and event_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_snapshot(), event_loop)


def sync_ticker_subscriptions(ws: KiteTicker) -> None:
    data = read_snapshot()
    if not data:
        return
    tokens = {int(p["instrument_token"]) for group in ("day", "net")
              for p in data.get(group, []) if p.get("instrument_token")}
    new_tokens = sorted(tokens - subscribed_tokens)
    if new_tokens:
        ws.subscribe(new_tokens)
        ws.set_mode(ws.MODE_LTP, new_tokens)
        subscribed_tokens.update(new_tokens)


def start_ticker() -> None:
    global ticker, subscribed_tokens
    if not kite.authenticated or not kite.ticker_credentials:
        return
    stop_ticker()
    subscribed_tokens = set()
    api_key, access_token = kite.ticker_credentials
    stream = KiteTicker(api_key, access_token, reconnect=True, reconnect_max_tries=50, reconnect_max_delay=60)

    def connected(ws: KiteTicker, _: Any) -> None:
        subscribed_tokens.clear()
        sync_ticker_subscriptions(ws)

    stream.on_connect = connected
    stream.on_ticks = on_ticker_ticks
    stream.on_error = lambda _ws, code, reason: print(f"KiteTicker error {code}: {reason}")
    stream.on_close = lambda _ws, code, reason: print(f"KiteTicker closed {code}: {reason}")
    ticker = stream
    stream.connect(threaded=True)


def stop_ticker() -> None:
    global ticker, subscribed_tokens
    if ticker:
        with suppress(Exception):
            ticker.close()
        ticker = None
    subscribed_tokens.clear()


async def publish_positions() -> None:
    while True:
        if clients and kite.authenticated:
            try:
                data = await run_in_threadpool(make_snapshot)
                store_snapshot(data)
                if ticker:
                    sync_ticker_subscriptions(ticker)
                await broadcast_snapshot()
            except Exception as exc:
                for client in list(clients):
                    with suppress(Exception):
                        await client.send_json({"type": "error", "message": str(exc)})
        await asyncio.sleep(refresh_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global event_loop
    event_loop = asyncio.get_running_loop()
    task = asyncio.create_task(publish_positions())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    stop_ticker()


app = FastAPI(
    title="Positions Intelligence API",
    description="Read-only intraday and net positions from Zerodha Kite Connect.",
    version="0.3.0",
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
        await run_in_threadpool(kite.create_session, request_token)
        initial = await run_in_threadpool(make_snapshot)
        store_snapshot(initial)
        start_ticker()
    except Exception:
        stop_ticker()
        return RedirectResponse(url="/?login=failed", status_code=303)
    return RedirectResponse(url="/api/positions/intelligence", status_code=303)


@app.get("/", include_in_schema=False)
async def login_page(request_token: str | None = None, status: str | None = None,
                     action: str | None = None):
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
    return {"status": "ok", "kite_configured": bool(kite.api_key),
            "authenticated": kite.authenticated, "ticker_running": ticker is not None,
            "refresh_seconds": refresh_seconds}


@app.get("/api/auth/login")
async def auth_login():
    try:
        return {"login_url": kite.login_url()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/logout", include_in_schema=False)
async def logout():
    stop_ticker()
    kite.clear_session()
    store_snapshot(None)
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/positions/intelligence", include_in_schema=False)
async def positions_intelligence():
    if not kite.authenticated:
        return RedirectResponse(url="/", status_code=303)
    return FileResponse("app/static/positions.html")


@app.get("/api/positions/all")
@app.get("/api/positions/today")
async def today_positions():
    if not kite.authenticated:
        raise HTTPException(status_code=401, detail="Kite session is not authenticated. Complete the Kite login flow first.")
    try:
        data = await run_in_threadpool(make_snapshot)
        store_snapshot(data)
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}") from exc


@app.websocket("/ws/positions")
async def positions_socket(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        data = read_snapshot()
        if kite.authenticated:
            if data is None:
                data = await run_in_threadpool(make_snapshot)
                store_snapshot(data)
            await websocket.send_json({"type": "positions", "data": data})
        else:
            await websocket.send_json({"type": "error", "message": "Kite session is not authenticated. Please log in again."})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)
