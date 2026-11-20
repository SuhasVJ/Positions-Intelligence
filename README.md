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

Open `http://127.0.0.1:8001/` and sign in with Kite.

## Live market data

- Kite REST `positions()` provides the initial day/net position rows and the broker P&L baseline.
- KiteTicker subscribes to the instrument tokens currently present in both day and net positions using LTP mode.
- Every tick reprices the open quantity from the previous LTP, applying only the LTP delta to Kite's REST unrealised-P&L baseline. This avoids replacing the broker baseline with an approximation.
- FastAPI `/ws/positions` broadcasts updated day/net rows, summaries and timestamps to the browser.
- REST positions are reconciled every `POSITION_REFRESH_SECONDS` (default 30 seconds) to pick up changed quantities/new positions; newly appearing instrument tokens are subscribed automatically.
- The dashboard labels the feed as KiteTicker live prices or REST snapshot so a connected browser socket is not mistaken for a live market feed.

KiteTicker streams ticks only while the market/data feed is available and the access token is valid. This application is read-only and does not place, modify, or cancel orders.

## Endpoints

- `GET /` — login screen
- `GET /api/auth/login` — Kite login URL
- `GET /auth/callback` — Kite OAuth callback
- `GET /api/positions/intelligence` — positions dashboard (HTML)
- `GET /api/positions/all` — day and net positions JSON
- `GET /api/positions/today` — backward-compatible alias
- `WS /ws/positions` — live position snapshots
- `GET /api/health` — service and ticker health

The dashboard defaults to Kite's `net` collection and provides a separate `day` collection tab. The Kite access token is held in process memory and must be renewed after a server restart. Never commit `.env` or credentials.


## Daily realised P&L and charges

- The dashboard's **Realised P&L Today** is summed from Kite's `day` positions collection. The `net` collection remains the source for the net portfolio P&L and open net exposure.
- **Charges Today** are estimated from today's executed trades: the service groups fills by order, then calls Kite's `/charges/orders` virtual contract-note API to calculate brokerage, STT/CTT, exchange charges, SEBI charges, stamp duty and GST.
- These are estimates from Kite's virtual contract note, not the final contract-note/ledger debit. Final broker-posted charges can differ.
- If the charges endpoint is unavailable, position monitoring remains available and the UI reports charges as unavailable rather than showing a misleading zero.
