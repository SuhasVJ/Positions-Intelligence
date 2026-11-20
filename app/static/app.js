const $ = (id) => document.getElementById(id);
const money = (value) => Number(value || 0).toLocaleString("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 2
});

function showError(message) {
  const node = $("error");
  if (node) node.textContent = message || "";
}

async function startKiteLogin(button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Connecting to Kite…";
  showError("");
  try {
    const response = await fetch("/api/auth/login", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not start Kite login.");
    if (!data.login_url) throw new Error("Kite did not return a login URL.");
    window.location.assign(data.login_url);
  } catch (error) {
    showError(error.message || "Unable to start Kite login.");
    button.disabled = false;
    button.textContent = originalText;
  }
}

function initializeLoginPage() {
  const button = $("loginButton");
  if (!button) return false;
  button.addEventListener("click", () => startKiteLogin(button));
  const params = new URLSearchParams(window.location.search);
  if (params.get("login") === "failed") {
    showError("Kite authentication failed. Please try again and verify your Kite API credentials and redirect URL.");
  } else if (params.get("login") === "cancelled") {
    showError("Kite login was cancelled.");
  }
  return true;
}

function setPnlClass(node, value) {
  const amount = Number(value || 0);
  node.classList.toggle("positive", amount > 0);
  node.classList.toggle("negative", amount < 0);
}

function initializePositionsPage() {
  if (!$("positionsBody")) return;
  let socket;
  let snapshot = null;
  let activeView = "net";

  function renderSummary(data) {
    const summary = data.net_summary;
    const today = data.day_pnl || data.day_summary || { realised: 0 };
    [["totalPnl", summary.pnl], ["realised", today.realised], ["unrealised", summary.unrealised]]
      .forEach(([id, value]) => {
        const node = $(id);
        node.textContent = money(value);
        setPnlClass(node, value);
      });
    $("openCount").textContent = summary.open_positions;
    $("netCount").textContent = summary.position_count + " net position rows";
    $("netTabCount").textContent = data.net.length;
    $("dayTabCount").textContent = data.day.length;

    const funds = data.funds || {};
    const segments = funds.segments || {};
    [["equity", "equityCash", "cash"], ["equity", "equityLive", "live_balance"],
      ["equity", "equityNet", "net"], ["equity", "equityUtilised", "utilised"],
      ["commodity", "commodityCash", "cash"], ["commodity", "commodityLive", "live_balance"],
      ["commodity", "commodityNet", "net"], ["commodity", "commodityUtilised", "utilised"]]
      .forEach(([segment, id, field]) => {
        const node = $(id);
        node.textContent = funds.available && segments[segment] ? money(segments[segment][field]) : "Unavailable";
      });
    $("fundsNote").textContent = funds.available
      ? "Kite account balances · refreshed with REST snapshots and WebSocket updates"
      : "Funds unavailable: " + (funds.error || "Kite did not return margin data");

    const charges = data.day_charges || {};
    const chargeValue = charges.available ? money(charges.total) : "Unavailable";
    $("chargesTotal").textContent = chargeValue;
    $("chargesHint").textContent = charges.available
      ? (charges.estimated ? "Estimated · " + (charges.order_count || 0) + " executed orders" : "Today's charges")
      : "Kite charges endpoint unavailable";
    $("chargesTradeCount").textContent = charges.available
      ? (charges.trade_count || 0) + " executed trades"
      : "Not available";
    const breakdown = charges.breakdown || {};
    [["chargeBrokerage", breakdown.brokerage], ["chargeTax", breakdown.transaction_tax],
      ["chargeExchange", breakdown.exchange_turnover_charge], ["chargeSebi", breakdown.sebi_turnover_charge],
      ["chargeStamp", breakdown.stamp_duty], ["chargeGst", breakdown.gst]]
      .forEach(([id, value]) => { $(id).textContent = charges.available ? money(value) : "—"; });
  }

  function renderTable() {
    if (!snapshot) return;
    const positions = snapshot[activeView] || [];
    $("rowCount").textContent = positions.length + (positions.length === 1 ? " position" : " positions");
    const selectedPnl = positions.reduce((sum, position) => sum + Number(position.pnl || 0), 0);
    const pnlValue = $("pnlIndicatorValue");
    pnlValue.textContent = money(selectedPnl);
    setPnlClass(pnlValue, selectedPnl);

    // Scale the visual fill to ₹10,000; cap at 100% while colour communicates direction.
    const pnlFill = $("pnlIndicatorFill");
    const pnlMagnitude = Math.min(Math.abs(selectedPnl) / 10000, 1) * 100;
    pnlFill.style.width = pnlMagnitude + "%";
    pnlFill.classList.toggle("positive", selectedPnl > 0);
    pnlFill.classList.toggle("negative", selectedPnl < 0);
    pnlFill.classList.toggle("neutral", selectedPnl === 0);
    pnlFill.parentElement.parentElement.setAttribute(
      "aria-label",
      selectedPnl > 0 ? "Total profit " + money(selectedPnl) :
        selectedPnl < 0 ? "Total loss " + money(Math.abs(selectedPnl)) : "Total P&L break-even"
    );
    $("netTab").classList.toggle("active", activeView === "net");
    $("dayTab").classList.toggle("active", activeView === "day");
    $("netTab").setAttribute("aria-selected", String(activeView === "net"));
    $("dayTab").setAttribute("aria-selected", String(activeView === "day"));

    const body = $("positionsBody");
    if (!positions.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 5;
      cell.className = "empty";
      cell.textContent = activeView === "net" ? "No net positions were returned by Kite." : "No positions recorded for today.";
      row.appendChild(cell);
      body.replaceChildren(row);
      return;
    }

    const fragment = document.createDocumentFragment();
    positions.forEach((position) => {
      const row = document.createElement("tr");
      const values = [
        position.tradingsymbol || "—",
        position.quantity ?? 0,
        money(position.average_price),
        money(position.last_price),
        money(position.pnl)
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (index === 0) cell.classList.add("instrument");
        if (index > 0) cell.classList.add("number");
        if (index === 4) setPnlClass(cell, position.pnl);
        row.appendChild(cell);
      });
      fragment.appendChild(row);
    });
    body.replaceChildren(fragment);
  }

  function render(data) {
    snapshot = data;
    const feed = data.price_feed === "KiteTicker" ? "Live prices · KiteTicker" : "REST snapshot · waiting for market ticks";
    $("feedStatus").textContent = feed;
    renderSummary(data);
    renderTable();
    showError("");
  }

  async function refresh() {
    try {
      const response = await fetch("/api/positions/all", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to fetch positions from Kite.");
      render(data);
    } catch (error) {
      showError(error.message);
      $("positionsBody").innerHTML = '<tr><td colspan="5" class="empty">Could not load positions. Check the Kite session and refresh.</td></tr>';
    }
  }

  function connectSocket() {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws/positions`);
    socket.onopen = () => {
      $("feedStatus").textContent = "WebSocket connected · waiting for position updates";
    };
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "positions") render(message.data);
      else if (message.type === "error") showError(message.message);
    };
    socket.onclose = () => {
      $("feedStatus").textContent = "WebSocket disconnected · reconnecting";
      window.setTimeout(connectSocket, 3000);
    };
    socket.onerror = () => socket.close();
  }

  function applyTheme(theme) {
    const light = theme === "light";
    document.body.classList.toggle("theme-light", light);
    const button = $("themeToggle");
    button.textContent = light ? "Switch to dark theme" : "Switch to light theme";
    button.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
  }

  const savedTheme = localStorage.getItem("positions-intelligence-theme") || "dark";
  applyTheme(savedTheme);
  $("themeToggle").addEventListener("click", () => {
    const nextTheme = document.body.classList.contains("theme-light") ? "dark" : "light";
    localStorage.setItem("positions-intelligence-theme", nextTheme);
    applyTheme(nextTheme);
  });

  $("netTab").addEventListener("click", () => { activeView = "net"; renderTable(); });
  $("dayTab").addEventListener("click", () => { activeView = "day"; renderTable(); });
  $("logoutButton").addEventListener("click", () => { window.location.href = "/logout"; });

  refresh();
  connectSocket();
}

if (!initializeLoginPage()) initializePositionsPage();
