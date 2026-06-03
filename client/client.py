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
HEIGHT = CELL * GRID_H + 70   # 70px HUD

# ─── Warna ─────────────────────────────────────────────────
BG        = (10,  14,  26)
BG2       = (15,  21,  39)
GRID_COL  = (20,  30,  55)
WHITE     = (240, 240, 240)
DIM       = (80,  95,  130)
HUD_COL   = (12,  18,  32)
P1        = (0,   255, 136)
P1_DARK   = (0,   120, 60)
P1_HEAD   = (0,   255, 180)
P2        = (255, 60,  100)
P2_DARK   = (150, 20,  50)
P2_HEAD   = (255, 100, 130)
FOOD_COL  = (255, 215, 0)
FOOD_GLOW = (255, 215, 0,  80)

# ─── Kontrol ────────────────────────────────────────────────
CONTROLS = {
    1: {'UP': pygame.K_w, 'DOWN': pygame.K_s, 'LEFT': pygame.K_a, 'RIGHT': pygame.K_d},
    2: {'UP': pygame.K_UP, 'DOWN': pygame.K_DOWN, 'LEFT': pygame.K_LEFT, 'RIGHT': pygame.K_RIGHT},
}

# ─── State ─────────────────────────────────────────────────
clients = {}
lock    = threading.Lock()

# ─── Kirim input ───────────────────────────────────────────
def send_dir(sock, direction):
    try:
        sock.sendall((json.dumps({'type': 'dir', 'dir': direction}) + '\n').encode())
    except:
        pass

# ─── Render helpers ────────────────────────────────────────
def draw_grid(screen):
    for x in range(0, WIDTH, CELL):
        pygame.draw.line(screen, GRID_COL, (x, 0), (x, GRID_H * CELL))
    for y in range(0, GRID_H * CELL, CELL):
        pygame.draw.line(screen, GRID_COL, (0, y), (WIDTH, y))

def draw_snake(screen, snake, c_head, c_body, c_head_bright):
    for i, seg in enumerate(snake):
        x  = seg['x'] * CELL + 1
        y  = seg['y'] * CELL + 1
        sz = CELL - 2
        col = c_head if i == 0 else c_body
        pygame.draw.rect(screen, col, (x, y, sz, sz), border_radius=6 if i == 0 else 4)

        # Mata pada kepala
        if i == 0:
            eye1 = (x + int(sz * 0.65), y + int(sz * 0.28))
            eye2 = (x + int(sz * 0.65), y + int(sz * 0.72))
            pygame.draw.circle(screen, (0, 0, 0), eye1, 3)
            pygame.draw.circle(screen, (0, 0, 0), eye2, 3)
            pygame.draw.circle(screen, WHITE, (eye1[0]-1, eye1[1]-1), 1)
            pygame.draw.circle(screen, WHITE, (eye2[0]-1, eye2[1]-1), 1)

def draw_food(screen, food, tick):
    if not food:
        return
    cx = food['x'] * CELL + CELL // 2
    cy = food['y'] * CELL + CELL // 2
    r  = CELL // 2 - 3

    # Animasi pulse
    pulse = 1 + 0.15 * math.sin(tick * 0.12)
    gr    = int(r * 1.8 * pulse)

    # Glow
    glow_surf = pygame.Surface((gr * 4, gr * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (255, 215, 0, 60), (gr * 2, gr * 2), gr)
    screen.blit(glow_surf, (cx - gr * 2, cy - gr * 2))

    # Makanan
    pygame.draw.circle(screen, FOOD_COL, (cx, cy), int(r * pulse))

    # Highlight
    pygame.draw.circle(screen, (255, 255, 200), (cx - r//3, cy - r//3), max(2, r//3))

def draw_hud(screen, font_hud, font_ctrl, players_data, prev_scores, score_flash):
    hud_y = GRID_H * CELL
    pygame.draw.rect(screen, HUD_COL, (0, hud_y, WIDTH, 70))
    pygame.draw.line(screen, GRID_COL, (0, hud_y), (WIDTH, hud_y), 1)
    pygame.draw.line(screen, GRID_COL, (WIDTH // 2, hud_y), (WIDTH // 2, hud_y + 70), 1)

    for p in players_data:
        pid   = p['id']
        alive = p['alive']
        score = p['score']
        ctrl  = "W A S D" if pid == 1 else "↑ ↓ ← →"
        col   = (P1 if pid == 1 else P2) if alive else DIM
        x_pos = 16 if pid == 1 else WIDTH // 2 + 16

        # Flash saat score naik
        if score_flash.get(pid, 0) > 0:
            flash_col = WHITE
        else:
            flash_col = col

        label = f"P{pid}  {score:02d} pts" + ("" if alive else "  [MATI]")
        screen.blit(font_hud.render(label,  True, flash_col), (x_pos, hud_y + 10))
        screen.blit(font_ctrl.render(ctrl,  True, DIM),       (x_pos, hud_y + 44))

def draw_overlay(screen, font_big, font_sm, message, sub="", col=WHITE):
    ov = pygame.Surface((WIDTH, GRID_H * CELL), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 170))
    screen.blit(ov, (0, 0))
    t1 = font_big.render(message, True, col)
    screen.blit(t1, t1.get_rect(center=(WIDTH // 2, GRID_H * CELL // 2 - 22)))
    if sub:
        t2 = font_sm.render(sub, True, DIM)
        screen.blit(t2, t2.get_rect(center=(WIDTH // 2, GRID_H * CELL // 2 + 26)))

# ─── Main ──────────────────────────────────────────────────
def main():
    global clients, GRID_W, GRID_H, WIDTH, HEIGHT

    # ── Konek 2 socket ke server ───────────────────────────
    socks = {}
    for pid in [1, 2]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((HOST, PORT))
            print(f"[+] Socket P{pid} terkonek")
        except Exception as e:
            print(f"[!] Gagal konek P{pid}: {e}")
            sys.exit(1)
        socks[pid] = sock
        clients[pid] = {'sock': sock, 'state': None}

    # ── Receiver thread ────────────────────────────────────
    init_received = {1: False, 2: False}

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
                            # Update grid size dari server
                            global GRID_W, GRID_H, WIDTH, HEIGHT
                            if 'grid_w' in msg:
                                GRID_W  = msg['grid_w']
                                GRID_H  = msg['grid_h']
                                WIDTH   = CELL * GRID_W
                                HEIGHT  = CELL * GRID_H + 70
                            init_received[pid] = True
                        with lock:
                            if msg['type'] in ('state', 'start', 'gameover', 'countdown'):
                                clients[pid]['state'] = msg
                    except:
                        pass
        except:
            pass

    for pid in [1, 2]:
        t = threading.Thread(target=receiver, args=(socks[pid], pid), daemon=True)
        t.start()

    print("[*] Menunggu server assign player id...")
    while not all(init_received.values()):
        time.sleep(0.05)
    print("[*] Kedua player siap!")

    # ── Init pygame ────────────────────────────────────────
    pygame.init()
    screen   = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake Battle  |  P1: WASD   P2: ↑↓←→")
    font_big  = pygame.font.SysFont('consolas', 44, bold=True)
    font_sm   = pygame.font.SysFont('consolas', 20)
    font_hud  = pygame.font.SysFont('consolas', 20, bold=True)
    font_ctrl = pygame.font.SysFont('consolas', 14)
    fps_clock = pygame.time.Clock()

    game_over   = False
    winner_msg  = ""
    winner_col  = WHITE
    tick        = 0
    prev_scores = {1: 0, 2: 0}
    score_flash = {1: 0, 2: 0}  # flash timer per player

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
                # Tekan R untuk restart setelah game over
                if game_over and event.key == pygame.K_r:
                    for sock in socks.values():
                        sock.close()
                    pygame.quit()
                    main()
                    return

        with lock:
            current_state = clients[1]['state']

        # ── Render ────────────────────────────────────────
        screen.fill(BG)
        draw_grid(screen)

        if current_state:
            stype        = current_state.get('type')
            players_data = current_state.get('players', [])

            # Update score flash
            for p in players_data:
                pid = p['id']
                if p['score'] != prev_scores[pid]:
                    score_flash[pid] = 12  # flash 12 frame
                    prev_scores[pid] = p['score']
                if score_flash[pid] > 0:
                    score_flash[pid] -= 1

            # Makanan — hanya saat game berjalan
            if stype == 'state':
                food = current_state.get('food')
                draw_food(screen, food, tick)

            # Ular
            for p in players_data:
                snake = p.get('snake', [])
                if not snake:
                    continue
                if p['id'] == 1:
                    draw_snake(screen, snake, P1, P1_DARK, P1_HEAD)
                else:
                    draw_snake(screen, snake, P2, P2_DARK, P2_HEAD)

            # HUD
            draw_hud(screen, font_hud, font_ctrl, players_data, prev_scores, score_flash)

            # Overlay
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
                draw_overlay(screen, font_big, font_sm, winner_msg, "Tekan R untuk main lagi", winner_col)
            elif stype == 'countdown':
                count = current_state.get('count', '')
                draw_overlay(screen, font_big, font_sm, str(count), "Bersiap...", FOOD_COL)
            elif stype == 'start':
                draw_overlay(screen, font_big, font_sm, "GO!", "", P1)

        else:
            draw_overlay(screen, font_big, font_sm, "Menunggu...", "Connecting to server", DIM)

        pygame.display.flip()

if __name__ == '__main__':
    main()