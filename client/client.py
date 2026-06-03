import socket
import threading
import json
import pygame
import sys
import time
import math

# ─── Konfigurasi ───────────────────────────────────────────
HOST   = '127.0.0.1'
PORT   = 5555
CELL   = 25
GRID_W = 30
GRID_H = 25
WIDTH  = CELL * GRID_W
HEIGHT = CELL * GRID_H + 70

# ─── Warna ─────────────────────────────────────────────────
BG       = (10,  14,  26)
GRID_COL = (20,  30,  55)
WHITE    = (240, 240, 240)
DIM      = (80,  95,  130)
HUD_COL  = (12,  18,  32)
P1       = (0,   255, 136)
P1_DARK  = (0,   120, 60)
P2       = (255, 60,  100)
P2_DARK  = (150, 20,  50)
FOOD_COL = (255, 215, 0)

# ─── Kontrol ───────────────────────────────────────────────
CONTROLS = {
    1: {'UP': pygame.K_w, 'DOWN': pygame.K_s, 'LEFT': pygame.K_a, 'RIGHT': pygame.K_d},
    2: {'UP': pygame.K_UP, 'DOWN': pygame.K_DOWN, 'LEFT': pygame.K_LEFT, 'RIGHT': pygame.K_RIGHT},
}

# ─── Kirim input ───────────────────────────────────────────
def send_dir(sock, direction):
    try:
        sock.sendall((json.dumps({'type': 'dir', 'dir': direction}) + '\n').encode())
    except:
        pass

# ─── Render helpers ────────────────────────────────────────
def draw_grid(screen, grid_w, grid_h, cell):
    for x in range(0, grid_w * cell, cell):
        pygame.draw.line(screen, GRID_COL, (x, 0), (x, grid_h * cell))
    for y in range(0, grid_h * cell, cell):
        pygame.draw.line(screen, GRID_COL, (0, y), (grid_w * cell, y))

def draw_snake(screen, snake, c_head, c_body, cell):
    for i, seg in enumerate(snake):
        x  = seg['x'] * cell + 1
        y  = seg['y'] * cell + 1
        sz = cell - 2
        pygame.draw.rect(screen, c_head if i == 0 else c_body,
                         (x, y, sz, sz), border_radius=6 if i == 0 else 4)
        if i == 0:
            ex = x + int(sz * 0.65)
            pygame.draw.circle(screen, (0, 0, 0), (ex, y + int(sz * 0.28)), 3)
            pygame.draw.circle(screen, (0, 0, 0), (ex, y + int(sz * 0.72)), 3)
            pygame.draw.circle(screen, WHITE,     (ex - 1, y + int(sz * 0.28) - 1), 1)
            pygame.draw.circle(screen, WHITE,     (ex - 1, y + int(sz * 0.72) - 1), 1)

def draw_food(screen, food, tick, cell):
    if not food:
        return
    cx = food['x'] * cell + cell // 2
    cy = food['y'] * cell + cell // 2
    r  = cell // 2 - 3
    pulse = 1 + 0.15 * math.sin(tick * 0.12)
    gr    = int(r * 1.8 * pulse)
    glow  = pygame.Surface((gr * 4, gr * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 215, 0, 55), (gr * 2, gr * 2), gr)
    screen.blit(glow, (cx - gr * 2, cy - gr * 2))
    pygame.draw.circle(screen, FOOD_COL, (cx, cy), int(r * pulse))
    pygame.draw.circle(screen, (255, 255, 200), (cx - r//3, cy - r//3), max(2, r//3))

def draw_hud(screen, fonts, players_data, width, grid_h, cell, score_flash):
    hud_y = grid_h * cell
    pygame.draw.rect(screen, HUD_COL, (0, hud_y, width, 70))
    pygame.draw.line(screen, GRID_COL, (0, hud_y), (width, hud_y), 1)
    pygame.draw.line(screen, GRID_COL, (width // 2, hud_y), (width // 2, hud_y + 70), 1)
    for p in players_data:
        pid   = p['id']
        alive = p['alive']
        col   = (P1 if pid == 1 else P2) if alive else DIM
        flash = score_flash.get(pid, 0) > 0
        x_pos = 16 if pid == 1 else width // 2 + 16
        ctrl  = "W A S D" if pid == 1 else "↑ ↓ ← →"
        label = f"P{pid}  {p['score']:02d} pts" + ("" if alive else "  [MATI]")
        screen.blit(fonts['hud'].render(label, True, WHITE if flash else col), (x_pos, hud_y + 10))
        screen.blit(fonts['ctrl'].render(ctrl,  True, DIM),                    (x_pos, hud_y + 44))

def draw_overlay(screen, fonts, width, grid_h, cell, message, sub="", col=WHITE):
    total_h = grid_h * cell + 70   # nutup arena + HUD
    ov = pygame.Surface((width, total_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 190))
    screen.blit(ov, (0, 0))
    cx = width // 2
    cy = total_h // 2              # tengah layar penuh
    t1 = fonts['big'].render(message, True, col)
    screen.blit(t1, t1.get_rect(center=(cx, cy - 22)))
    if sub:
        t2 = fonts['sm'].render(sub, True, DIM)
        screen.blit(t2, t2.get_rect(center=(cx, cy + 26)))

# ─── Koneksi ───────────────────────────────────────────────
def connect_sockets():
    """Buat 2 koneksi socket ke server. Return (socks, grid_w, grid_h) atau raise Exception."""
    socks         = {}
    init_received = {1: False, 2: False}
    grid_info     = {}
    clients       = {}
    lock          = threading.Lock()

    def receiver(sock, pid):
        buffer = ''
        try:
            while True:
                data = sock.recv(4096).decode()
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg['type'] == 'init':
                            print(f"[*] P{pid} → Player {msg['player_id']}")
                            if 'grid_w' in msg:
                                grid_info['w'] = msg['grid_w']
                                grid_info['h'] = msg['grid_h']
                            init_received[pid] = True
                        with lock:
                            if msg['type'] in ('state', 'start', 'gameover', 'countdown'):
                                clients[pid] = msg
                    except:
                        pass
        except:
            pass

    for pid in [1, 2]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        print(f"[+] Socket P{pid} terkonek")
        socks[pid] = sock
        t = threading.Thread(target=receiver, args=(sock, pid), daemon=True)
        t.start()

    # Tunggu init kedua socket
    timeout = time.time() + 10
    while not all(init_received.values()):
        if time.time() > timeout:
            raise Exception("Timeout menunggu init dari server")
        time.sleep(0.05)

    gw = grid_info.get('w', GRID_W)
    gh = grid_info.get('h', GRID_H)
    return socks, clients, lock, gw, gh

# ─── Main ──────────────────────────────────────────────────
def main():
    # Loop luar untuk handle restart tanpa rekursi
    while True:
        run_game()

def run_game():
    # ── Konek ke server ────────────────────────────────────
    print("[*] Menghubungkan ke server...")
    try:
        socks, clients, lock, gw, gh = connect_sockets()
    except Exception as e:
        print(f"[!] Gagal konek: {e}")
        sys.exit(1)

    print("[*] Kedua player siap!")

    w = CELL * gw
    h = CELL * gh + 70

    # ── Init pygame ────────────────────────────────────────
    pygame.init()
    screen = pygame.display.set_mode((w, h))
    pygame.display.set_caption("Snake Battle  |  P1: WASD   P2: ↑↓←→")

    fonts = {
        'big':  pygame.font.SysFont('consolas', 44, bold=True),
        'sm':   pygame.font.SysFont('consolas', 20),
        'hud':  pygame.font.SysFont('consolas', 20, bold=True),
        'ctrl': pygame.font.SysFont('consolas', 14),
    }

    fps_clock   = pygame.time.Clock()
    game_over   = False
    go_timer    = 0       # timer untuk GO! overlay
    winner_msg  = ""
    winner_col  = WHITE
    tick        = 0
    prev_scores = {1: 0, 2: 0}
    score_flash = {1: 0, 2: 0}

    # ── Game loop ──────────────────────────────────────────
    while True:
        fps_clock.tick(60)
        tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                for sock in socks.values():
                    sock.close()
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if not game_over:
                    for dir_name, key in CONTROLS[1].items():
                        if event.key == key:
                            send_dir(socks[1], dir_name)
                    for dir_name, key in CONTROLS[2].items():
                        if event.key == key:
                            send_dir(socks[2], dir_name)

                # R = restart setelah game over
                if game_over and event.key == pygame.K_r:
                    for sock in socks.values():
                        try: sock.close()
                        except: pass
                    pygame.quit()
                    return  # kembali ke loop luar → run_game() dipanggil lagi

        with lock:
            current_state = clients.get(1)

        # ── Render ────────────────────────────────────────
        screen.fill(BG)
        draw_grid(screen, gw, gh, CELL)

        if current_state:
            stype        = current_state.get('type')
            players_data = current_state.get('players', [])

            # Score flash
            for p in players_data:
                pid = p['id']
                if p['score'] != prev_scores[pid]:
                    score_flash[pid] = 12
                    prev_scores[pid] = p['score']
                if score_flash[pid] > 0:
                    score_flash[pid] -= 1

            # Makanan
            if stype == 'state':
                draw_food(screen, current_state.get('food'), tick, CELL)

            # Ular
            for p in players_data:
                snake = p.get('snake', [])
                if not snake:
                    continue
                if p['id'] == 1:
                    draw_snake(screen, snake, P1, P1_DARK, CELL)
                else:
                    draw_snake(screen, snake, P2, P2_DARK, CELL)

            # HUD
            draw_hud(screen, fonts, players_data, w, gh, CELL, score_flash)

            # Overlay logic
            if stype == 'gameover' and not game_over:
                game_over = True
                winner    = current_state.get('winner')
                if winner is None:
                    winner_msg = "SERI!"
                    winner_col = FOOD_COL
                else:
                    winner_msg = f"P{winner} MENANG!"
                    winner_col = P1 if winner == 1 else P2

            if game_over:
                draw_overlay(screen, fonts, w, gh, CELL,
                             winner_msg, "Tekan R untuk main lagi", winner_col)
            elif stype == 'start':
                # Tampilkan GO! selama 90 frame (~1.5 detik)
                if go_timer < 90:
                    go_timer += 1
                    draw_overlay(screen, fonts, w, gh, CELL, "GO!", "", P1)
            elif stype == 'countdown':
                count = current_state.get('count', '')
                draw_overlay(screen, fonts, w, gh, CELL,
                             str(count), "Bersiap...", FOOD_COL)

        else:
            draw_overlay(screen, fonts, w, gh, CELL,
                         "Menunggu...", "Connecting to server...", DIM)

        pygame.display.flip()

if __name__ == '__main__':
    main()