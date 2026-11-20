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
    [["totalPnl", summary.pnl], ["realised", summary.realised], ["unrealised", summary.unrealised]]
      .forEach(([id, value]) => {
        const node = $(id);
        node.textContent = money(value);
        setPnlClass(node, value);
      });
    $("openCount").textContent = summary.open_positions;
    $("netCount").textContent = summary.position_count + " net position rows";
    $("netTabCount").textContent = data.net.length;
    $("dayTabCount").textContent = data.day.length;
  }

  function renderTable() {
    if (!snapshot) return;
    const positions = snapshot[activeView] || [];
    $("rowCount").textContent = positions.length + (positions.length === 1 ? " position" : " positions");
    $("netTab").classList.toggle("active", activeView === "net");
    $("dayTab").classList.toggle("active", activeView === "day");
    $("netTab").setAttribute("aria-selected", String(activeView === "net"));
    $("dayTab").setAttribute("aria-selected", String(activeView === "day"));

    const body = $("positionsBody");
    if (!positions.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 9;
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
        position.tradingsymbol || "—", position.exchange || "—", position.product || "—",
        position.quantity ?? 0, money(position.average_price), money(position.last_price),
        money(position.realised), money(position.unrealised), money(position.pnl)
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (index === 0) cell.classList.add("instrument");
        if (index >= 3) cell.classList.add("number");
        if (index >= 6) setPnlClass(cell, [position.realised, position.unrealised, position.pnl][index - 6]);
        row.appendChild(cell);
      });
      fragment.appendChild(row);
    });
    body.replaceChildren(fragment);
  }

  function render(data) {
    snapshot = data;
    $("asOf").textContent = "Last updated: " + new Date(data.as_of).toLocaleString("en-IN");
    const feed = data.price_feed === "KiteTicker" ? "Live prices · KiteTicker" : "WebSocket connected · REST snapshot";
    $("connection").innerHTML = "<i></i> " + feed;
    $("connection").classList.add("connected");
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
      $("positionsBody").innerHTML = '<tr><td colspan="9" class="empty">Could not load positions. Check the Kite session and refresh.</td></tr>';
    }
  }

  function connectSocket() {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws/positions`);
    socket.onopen = () => {
      $("connection").innerHTML = "<i></i> Live";
      $("connection").classList.add("connected");
    };
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "positions") render(message.data);
      else if (message.type === "error") showError(message.message);
    };
    socket.onclose = () => {
      $("connection").innerHTML = "<i></i> Reconnecting";
      $("connection").classList.remove("connected");
      window.setTimeout(connectSocket, 3000);
    };
    socket.onerror = () => socket.close();
  }

  $("netTab").addEventListener("click", () => { activeView = "net"; renderTable(); });
  $("dayTab").addEventListener("click", () => { activeView = "day"; renderTable(); });
  $("refreshButton").addEventListener("click", refresh);
  $("logoutButton").addEventListener("click", () => { window.location.href = "/logout"; });

  refresh();
  connectSocket();
}

if (!initializeLoginPage()) initializePositionsPage();
