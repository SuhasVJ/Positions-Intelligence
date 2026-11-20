const $ = (id) => document.getElementById(id);
const money = (value) => Number(value || 0).toLocaleString("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 2
});
let socket;
let snapshot = null;
let activeView = "net";

function setPnlClass(node, value) {
  const amount = Number(value || 0);
  node.classList.toggle("positive", amount > 0);
  node.classList.toggle("negative", amount < 0);
}

function showError(message) {
  $("error").textContent = message || "";
}

function renderSummary(data) {
  const summary = data.net_summary;
  const values = [
    ["totalPnl", summary.pnl],
    ["realised", summary.realised],
    ["unrealised", summary.unrealised]
  ];
  values.forEach(([id, value]) => {
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
    cell.textContent = activeView === "net"
      ? "No net positions were returned by Kite."
      : "No positions recorded for today.";
    row.appendChild(cell);
    body.replaceChildren(row);
    return;
  }

  const fragment = document.createDocumentFragment();
  positions.forEach((position) => {
    const row = document.createElement("tr");
    const values = [
      position.tradingsymbol || "—",
      position.exchange || "—",
      position.product || "—",
      position.quantity ?? 0,
      money(position.average_price),
      money(position.last_price),
      money(position.realised),
      money(position.unrealised),
      money(position.pnl)
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
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws/positions`);
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
$("logoutButton").addEventListener("click", () => { location.href = "/logout"; });

refresh();
connectSocket();
