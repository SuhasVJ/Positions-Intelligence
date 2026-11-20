# Positions Intelligence

A minimal, read-only Python service for Zerodha Kite intraday and net positions.

## Run locally (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `KITE_API_KEY` and `KITE_API_SECRET` in `.env`, then run:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Set the Kite Connect app redirect URL to exactly `http://127.0.0.1:8001/auth/callback`.

Open `http://127.0.0.1:8001/`. The page contains only **Login with Kite**. After successful Kite authentication, the callback exchanges the request token server-side and redirects to `/api/positions/intelligence`.

## Endpoints

- `GET /` — login screen
- `GET /api/auth/login` — Kite login URL
- `GET /auth/callback` — Kite OAuth callback
- `GET /api/positions/intelligence` — positions dashboard (HTML)
- `GET /api/positions/all` — day and net positions JSON (preferred)
- `GET /api/positions/today` — backward-compatible alias returning the same snapshot
- `WS /ws/positions` — refreshed position snapshots
- `GET /api/health` — service health

The dashboard defaults to Kite's `net` collection (aggregated positions across trading days) and provides a separate `day` collection tab for today's intraday activity. WebSocket snapshots include both collections and are refreshed by polling Kite's positions endpoint at `POSITION_REFRESH_SECONDS` (default 5). This service does not place, modify, or cancel orders.

The Kite access token is held in process memory and must be renewed after a server restart. Never commit `.env` or credentials.
