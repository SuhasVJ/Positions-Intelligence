const $=id=>document.getElementById(id);
const money=value=>Number(value||0).toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2});
const signed=value=>Number(value)>0?"positive":Number(value)<0?"negative":"";
let socket;
function showError(message){const node=$("error");if(node)node.textContent=message||"";}
async function login(){try{const response=await fetch("/api/auth/login");const data=await response.json();if(!response.ok)throw new Error(data.detail||"Could not start Kite login");location.href=data.login_url;}catch(error){showError(error.message);}}
function render(snapshot){
 const {positions,summary,as_of:asOf}=snapshot;
 $("asOf").textContent="Last updated: "+new Date(asOf).toLocaleString("en-IN");
 for(const [id,value] of [["totalPnl",summary.pnl],["realised",summary.realised],["unrealised",summary.unrealised]]){$(id).textContent=money(value);$(id).className=signed(value);}
 $("openCount").textContent=summary.open_positions;$("rowCount").textContent=positions.length+" positions";
 const body=$("positionsBody");
 if(!positions.length){body.innerHTML='<tr><td colspan="9" class="empty">No positions for today.</td></tr>';return;}
 body.replaceChildren(...positions.map(p=>{const row=document.createElement("tr");const values=[p.tradingsymbol||"—",p.exchange||"—",p.product||"—",p.quantity,money(p.average_price),money(p.last_price),money(p.realised),money(p.unrealised),money(p.pnl)];values.forEach((value,index)=>{const cell=document.createElement("td");cell.textContent=value;if(index===0)cell.className="instrument";if(index>=3)cell.classList.add("number");if(index>=6)cell.classList.add(signed([null,null,null,null,null,null,p.realised,p.unrealised,p.pnl][index]));row.appendChild(cell);});return row;}));
}
async function refresh(){try{const response=await fetch("/api/positions/today");const data=await response.json();if(!response.ok)throw new Error(data.detail||"Could not load positions");render(data);showError("");}catch(error){showError(error.message);}}
function connectSocket(){const scheme=location.protocol==="https:"?"wss":"ws";socket=new WebSocket(`${scheme}://${location.host}/ws/positions`);socket.onopen=()=>{$("connection").textContent="Live";$("connection").classList.add("connected");};socket.onclose=()=>{$("connection").textContent="Disconnected";$("connection").classList.remove("connected");};socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.type==="positions"){render(message.data);showError("");}else if(message.type==="error")showError(message.message);};}
const loginButton=$("loginButton");if(loginButton)loginButton.addEventListener("click",login);
const logoutButton=$("logoutButton");if(logoutButton)logoutButton.addEventListener("click",()=>{location.href="/logout";});
if($("positionsBody")){refresh();connectSocket();}
