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


## Funds and margins

- `GET /api/funds` returns the authenticated Kite account's equity and commodity funds/margin details.
- The response includes available cash, opening balance, live balance, collateral, intraday pay-in, net available margin, utilised debits, realised/unrealised M2M, SPAN and exposure.
- The positions dashboard displays equity and commodity balances separately. These segment balances are not combined into one spendable cash figure.
- Funds are included in the `/api/positions/all` REST snapshot and `/ws/positions` WebSocket payload. They refresh on the configured account snapshot interval (`POSITION_REFRESH_SECONDS`, default 30 seconds), not on every market tick.
- Data source: Kite Connect `GET /user/margins`. This is a read-only account margin snapshot, not a bank ledger or withdrawal balance.


## PortfolioIntelligence architecture

PortfolioIntelligence is a read-only analysis layer over the broker position snapshot and shared KiteTicker feed. It uses specialized evaluators per asset class and a common, explainable result contract. The selected scoring approach is hybrid: deterministic rules and quantitative analytics produce the score; AI-generated explanations may summarize those results but must not invent missing inputs. Adaptive scoring is event-driven, with tick updates marking affected positions dirty and configurable throttling before recalculation.

### Position Intelligence milestones

- **PI-1 — Position classification (current):** enrich positions using Kite's instrument master; classify equity, index options, stock options, index futures, stock futures, currency options/futures and commodity options/futures; normalize long/short/flat direction; expose classified open net positions.
- **PI-2 — Shared analytics:** reusable trend, momentum, volatility, liquidity and risk/reward features with explicit data freshness.
- **PI-3 — Equity and futures scorers:** asset-specific deterministic scoring and component explanations.
- **PI-4 — Options scorer:** directional Greeks, IV, theta, gamma, expiry and liquidity-aware scoring.
- **PI-5 — Commodity scorer:** MCX-specific contract, expiry, liquidity and volatility treatment.
- **PI-6 — Adaptive live scoring:** reuse KiteTicker ticks, throttle material recalculations and publish score events over WebSocket.
- **PI-7 — Portfolio-level intelligence:** concentration, correlation, combined exposure and strategy/hedge grouping.
- **PI-8 — Validation and calibration:** historical replay, regression fixtures, score stability and model-version tracking.

### PI-1 classification contract

- Kite instrument-master metadata is cached in process and keyed by `(exchange, tradingsymbol)`; positions are never classified from symbol text alone.
- A missing or unsupported instrument mapping is returned as `UNKNOWN` with zero classification confidence. It is not assigned a fabricated asset class.
- Direction is based on signed net quantity: positive = `LONG`, negative = `SHORT`, zero = `FLAT`.
- `GET /api/intelligence/positions` returns open net positions with classification metadata and classification coverage counts.
- The existing `/ws/positions` event includes the enriched classifications because the same classified snapshot is broadcast to the existing dashboard. Dedicated score events and adaptive scoring are deferred to PI-6.
- PI-1 does not calculate an intelligence score. The API explicitly returns `scoring_status: NOT_EVALUATED` until the required analytics and scorer milestones are implemented.
- Instrument metadata can be invalidated and refreshed after a broker instrument-master rollover.

### PI-1 tests

Run the regression suite with:

```powershell
python -m unittest discover -s tests -v
```

PI-1 tests cover all supported asset classes, long/short/flat direction, unknown metadata, cached instrument-master lookup, and the authenticated open-position intelligence endpoint.
