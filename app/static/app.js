const $ = (id) => document.getElementById(id);
const money = (value) => Number(value || 0).toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const signedClass = (value) => Number(value) > 0 ? "positive" : Number(value) < 0 ? "negative" : "";
let socket;

function setConnection(connected) {
  $("connection").textContent = connected ? "Live · WebSocket" : "Disconnected";
  $("connection").classList.toggle("connected", connected);
}

function render(snapshot) {
  const { positions, summary, as_of: asOf } = snapshot;
  $("asOf").textContent = "Last updated: " + new Date(asOf).toLocaleString("en-IN");
  $("totalPnl").textContent = money(summary.pnl);
  $("realised").textContent = money(summary.realised);
  $("unrealised").textContent = money(summary.unrealised);
  $("openCount").textContent = summary.open_positions;
  $("totalPnl").className = signedClass(summary.pnl);
  $("realised").className = signedClass(summary.realised);
  $("unrealised").className = signedClass(summary.unrealised);
  $("rowCount").textContent = positions.length + " positions";

  const body = $("positionsBody");
  if (!positions.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty">No positions for today.</td></tr>';
    return;
  }
  body.replaceChildren(...positions.map((p) => {
    const row = document.createElement("tr");
    const cells = [
      p.tradingsymbol || "—", p.exchange || "—", p.product || "—",
      p.quantity, money(p.average_price), money(p.last_price),
      money(p.realised), money(p.unrealised), money(p.pnl)
    ];
    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 0) cell.className = "instrument";
      if (index >= 3) cell.classList.add("number");
      if (index === 6 || index === 7 || index === 8) cell.classList.add(signedClass(index === 6 ? p.realised : index === 7 ? p.unrealised : p.pnl));
      row.appendChild(cell);
    });
    return row;
  }));
}

function showError(message) { $("error").textContent = message || ""; }

async function refresh() {
  try {
    const response = await fetch("/api/positions/today");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to fetch positions");
    render(data);
    showError("");
  } catch (error) { showError(error.message); }
}

function connectSocket() {
  if (socket && socket.readyState <= WebSocket.OPEN) socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws/positions`);
  socket.onopen = () => setConnection(true);
  socket.onclose = () => setConnection(false);
  socket.onerror = () => setConnection(false);
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "positions") { render(message.data); showError(""); }
    if (message.type === "error") showError(message.message);
  };
}

$("loginButton").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/auth/login");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to start Kite login");
    window.location.href = data.login_url;
  } catch (error) { showError(error.message); }
});

$("refreshButton").addEventListener("click", refresh);

(async function init() {
  const requestToken = new URLSearchParams(location.search).get("request_token");
  if (requestToken) {
    try {
      const response = await fetch("/api/auth/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_token: requestToken })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Kite authentication failed");
      history.replaceState({}, "", "/");
      showError("Connected to Kite successfully.");
    } catch (error) { showError(error.message); }
  }
  await refresh();
  connectSocket();
})();
