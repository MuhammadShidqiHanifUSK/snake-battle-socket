// ─── Koneksi WebSocket ──────────────────────────────────────
const WS_URL = "ws://localhost:8765";
let sockets = {};
let myState = null;
let gameOver = false;
let reconnecting = false;

// ─── Canvas setup ───────────────────────────────────────────
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const CELL = 22;
let GRID_W = 30;
let GRID_H = 25;

// ─── Warna ──────────────────────────────────────────────────
const COLORS = {
  bg: "#0a0e1a",
  grid: "rgba(30,45,80,0.25)",
  p1: "#00ff88",
  p1Dark: "#00994d",
  p1Head: "#00ffaa",
  p2: "#ff4466",
  p2Dark: "#cc1133",
  p2Head: "#ff6688",
  food: "#ffd700",
  foodGlow: "rgba(255,215,0,0.6)",
};

// ─── Kontrol ────────────────────────────────────────────────
const CONTROLS = {
  KeyW: { pid: 1, dir: "UP" },
  KeyS: { pid: 1, dir: "DOWN" },
  KeyA: { pid: 1, dir: "LEFT" },
  KeyD: { pid: 1, dir: "RIGHT" },
  ArrowUp: { pid: 2, dir: "UP" },
  ArrowDown: { pid: 2, dir: "DOWN" },
  ArrowLeft: { pid: 2, dir: "LEFT" },
  ArrowRight: { pid: 2, dir: "RIGHT" },
};

// ─── DOM elements ───────────────────────────────────────────
const overlay = document.getElementById("overlay");
const overlayTitle = document.getElementById("overlayTitle");
const overlaySub = document.getElementById("overlaySub");
const overlayDots = document.getElementById("overlayDots");
const connDot = document.getElementById("conn-dot");
const connText = document.getElementById("conn-text");
const scoreP1 = document.getElementById("score-p1");
const scoreP2 = document.getElementById("score-p2");
const cardP1 = document.getElementById("card-p1");
const cardP2 = document.getElementById("card-p2");

// ─── Helpers ────────────────────────────────────────────────
function setupCanvas(gw, gh) {
  GRID_W = gw;
  GRID_H = gh;
  canvas.width = CELL * GRID_W;
  canvas.height = CELL * GRID_H;
}

function setConnStatus(status, text) {
  connDot.className = status;
  connText.textContent = text;
}

function showOverlay(titleText, titleClass, subText, showDots = false) {
  overlay.classList.remove("hidden");
  overlayTitle.textContent = titleText;
  overlayTitle.className = "overlay-title " + titleClass;
  overlaySub.textContent = subText;
  overlayDots.style.display = showDots ? "flex" : "none";
}

function hideOverlay() {
  overlay.classList.add("hidden");
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Reconnect logic ────────────────────────────────────────
async function startReconnectLoop() {
  if (reconnecting) return;
  reconnecting = true;

  let attempt = 1;
  while (true) {
    showOverlay(
      "RECONNECTING...",
      "waiting",
      `Mencoba koneksi ulang... (${attempt})`,
      true,
    );
    setConnStatus("", `Reconnecting... (${attempt})`);

    try {
      await initGame();
      reconnecting = false;
      return;
    } catch (e) {
      console.warn(`[!] Reconnect gagal (${attempt}):`, e.message);
      attempt++;
      await sleep(3000); // tunggu 3 detik sebelum coba lagi
    }
  }
}

// ─── Handle pesan dari server ───────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case "countdown":
      myState = msg;
      showOverlay(msg.count.toString(), "countdown", "BERSIAP...", false);
      break;

    case "start":
      myState = msg;
      hideOverlay();
      break;

    case "state":
      myState = msg;
      updateHUD(msg.players);
      break;

    case "gameover":
      gameOver = true;
      myState = msg;
      const w = msg.winner;
      if (w === null) {
        showOverlay("SERI!", "draw", "Kedua pemain mati bersamaan", false);
      } else if (w === 1) {
        showOverlay("P1 MENANG!", "win-p1", "WASD wins this round", false);
      } else {
        showOverlay(
          "P2 MENANG!",
          "win-p2",
          "Arrow Keys wins this round",
          false,
        );
      }
      // Setelah game over, tunggu lalu reconnect otomatis
      setTimeout(() => {
        gameOver = false;
        myState = null;
        sockets = {};
        resetHUD();
        startReconnectLoop();
      }, 4000);
      break;

    case "error":
      // Server penuh — coba lagi sebentar lagi
      showOverlay("MENUNGGU...", "waiting", msg.msg, true);
      break;
  }
}

// ─── Update HUD skor ────────────────────────────────────────
let prevScores = { 1: 0, 2: 0 };

function resetHUD() {
  scoreP1.textContent = "00";
  scoreP2.textContent = "00";
  prevScores = { 1: 0, 2: 0 };
  cardP1.className = "score-card p1 alive";
  cardP2.className = "score-card p2 alive";
}

function updateHUD(players) {
  players.forEach((p) => {
    const el = p.id === 1 ? scoreP1 : scoreP2;
    const card = p.id === 1 ? cardP1 : cardP2;

    if (p.score !== prevScores[p.id]) {
      el.textContent = p.score.toString().padStart(2, "0");
      el.classList.remove("score-pop");
      void el.offsetWidth;
      el.classList.add("score-pop");
      prevScores[p.id] = p.score;
    }

    card.classList.toggle("alive", p.alive);
    card.classList.toggle("dead", !p.alive);
  });
}

// ─── Koneksi WebSocket ──────────────────────────────────────
function connectPlayer(pid) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL);
    const timeout = setTimeout(() => {
      ws.close();
      reject(new Error("Timeout konek ke server"));
    }, 5000);

    ws.onopen = () => {
      sockets[pid] = ws;
      console.log(`[+] Socket P${pid} terkonek`);
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "init") {
        clearTimeout(timeout);
        console.log(`[*] P${pid} assigned sebagai Player ${msg.player_id}`);
        if (msg.grid_w) setupCanvas(msg.grid_w, msg.grid_h);
        resolve(ws);
      } else if (msg.type === "error") {
        clearTimeout(timeout);
        reject(new Error(msg.msg));
      }
      handleMessage(msg);
    };

    ws.onerror = () => {
      clearTimeout(timeout);
      reject(
        new Error("Gagal konek ke server — pastikan server_ws.py berjalan"),
      );
    };

    ws.onclose = () => {
      if (!gameOver && !reconnecting) {
        setConnStatus("disconnected", "Koneksi terputus");
        startReconnectLoop();
      }
    };
  });
}

// ─── Init game ──────────────────────────────────────────────
async function initGame() {
  sockets = {};
  await connectPlayer(1);
  await sleep(150);
  await connectPlayer(2);

  setConnStatus("connected", "Terkonek — menunggu game...");
  showOverlay(
    "MENUNGGU...",
    "waiting",
    "Kedua pemain terkonek, game akan dimulai!",
    true,
  );
}

// ─── Render ─────────────────────────────────────────────────
function drawGrid() {
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 0.5;
  for (let x = 0; x <= GRID_W; x++) {
    ctx.beginPath();
    ctx.moveTo(x * CELL, 0);
    ctx.lineTo(x * CELL, GRID_H * CELL);
    ctx.stroke();
  }
  for (let y = 0; y <= GRID_H; y++) {
    ctx.beginPath();
    ctx.moveTo(0, y * CELL);
    ctx.lineTo(GRID_W * CELL, y * CELL);
    ctx.stroke();
  }
}

function drawSnake(snake, colorHead, colorBody) {
  snake.forEach((seg, i) => {
    const x = seg.x * CELL + 1;
    const y = seg.y * CELL + 1;
    const sz = CELL - 2;

    ctx.fillStyle = i === 0 ? colorHead : colorBody;
    ctx.beginPath();
    ctx.roundRect(x, y, sz, sz, i === 0 ? 6 : 4);
    ctx.fill();

    if (i === 0) {
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.beginPath();
      ctx.arc(x + sz * 0.65, y + sz * 0.3, 2.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x + sz * 0.65, y + sz * 0.7, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
  });
}

function drawFood(food) {
  if (!food) return;
  const cx = food.x * CELL + CELL / 2;
  const cy = food.y * CELL + CELL / 2;
  const r = CELL / 2 - 3;

  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 2);
  grad.addColorStop(0, COLORS.foodGlow);
  grad.addColorStop(1, "transparent");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, r * 2, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = COLORS.food;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.beginPath();
  ctx.arc(cx - r * 0.3, cy - r * 0.3, r * 0.35, 0, Math.PI * 2);
  ctx.fill();
}

function render() {
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  drawGrid();

  if (myState) {
    const stype = myState.type;
    const players = myState.players || [];

    if (stype === "state" && myState.food) drawFood(myState.food);

    players.forEach((p) => {
      if (!p.snake || p.snake.length === 0) return;
      if (p.id === 1) drawSnake(p.snake, COLORS.p1Head, COLORS.p1Dark);
      else drawSnake(p.snake, COLORS.p2Head, COLORS.p2Dark);
    });
  }

  requestAnimationFrame(render);
}

// ─── Input keyboard ─────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (gameOver) return;
  const ctrl = CONTROLS[e.code];
  if (!ctrl) return;
  e.preventDefault();
  const ws = sockets[ctrl.pid];
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "dir", dir: ctrl.dir }));
  }
});

// ─── Start ──────────────────────────────────────────────────
setupCanvas(GRID_W, GRID_H);
showOverlay("CONNECTING...", "waiting", "Menghubungkan ke server...", true);
setConnStatus("", "Menghubungkan...");
render();

initGame().catch((err) => {
  showOverlay("GAGAL KONEK", "waiting", err.message, false);
  setConnStatus("disconnected", "Gagal terkonek");
  // Tetap coba reconnect meski gagal pertama kali
  setTimeout(startReconnectLoop, 3000);
});
