import socket
import threading
import json
import pygame
import sys

# ─── Konfigurasi ───────────────────────────────────────────
HOST = '127.0.0.1'
PORT = 5555
CELL = 25
GRID_W = 30
GRID_H = 25
WIDTH  = CELL * GRID_W        # 750px
HEIGHT = CELL * GRID_H + 60   # 685px

# ─── Warna ─────────────────────────────────────────────────
BLACK      = (15,  15,  15)
WHITE      = (240, 240, 240)
GREEN      = (50,  200, 80)
GREEN_DARK = (30,  140, 50)
RED        = (220, 60,  60)
RED_DARK   = (160, 30,  30)
FOOD_COL   = (255, 210, 50)
GRID_COL   = (30,  30,  30)
HUD_COL    = (20,  20,  20)
TEXT_COL   = (200, 200, 200)

# ─── Kontrol per player ────────────────────────────────────
CONTROLS = {
    1: {
        'UP':    pygame.K_w,
        'DOWN':  pygame.K_s,
        'LEFT':  pygame.K_a,
        'RIGHT': pygame.K_d,
    },
    2: {
        'UP':    pygame.K_UP,
        'DOWN':  pygame.K_DOWN,
        'LEFT':  pygame.K_LEFT,
        'RIGHT': pygame.K_RIGHT,
    }
}

# ─── State per player ──────────────────────────────────────
clients = {}
lock = threading.Lock()

# ─── Fungsi kirim input ────────────────────────────────────
def send_dir(sock, direction):
    try:
        msg = json.dumps({'type': 'dir', 'dir': direction}) + '\n'
        sock.sendall(msg.encode())
    except:
        pass

# ─── Main ──────────────────────────────────────────────────
def main():
    global clients

    # ── Konek 2 socket ke server ───────────────────────────
    socks = {}
    for pid in [1, 2]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((HOST, PORT))
            print(f"[+] Socket P{pid} terkonek ke server")
        except Exception as e:
            print(f"[!] Gagal konek socket P{pid}: {e}")
            sys.exit(1)
        socks[pid] = sock
        clients[pid] = {'sock': sock, 'state': None}

    # ── Thread receiver per socket ─────────────────────────
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
                            print(f"[*] Socket P{pid} assigned sebagai Player {msg['player_id']}")
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

    # Tunggu kedua socket dapat init
    print("[*] Menunggu server assign player id...")
    import time
    while not all(init_received.values()):
        time.sleep(0.05)
    print("[*] Kedua player siap! Memulai pygame...")

    # ── Init pygame ────────────────────────────────────────
    pygame.init()
    screen   = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake Battle  |  P1: WASD    P2: Arrow Keys")
    font_hud = pygame.font.SysFont('consolas', 18, bold=True)
    font_big = pygame.font.SysFont('consolas', 42, bold=True)
    font_sm  = pygame.font.SysFont('consolas', 22)
    fps      = pygame.time.Clock()

    game_over  = False
    winner_msg = ""

    # ── Game loop pygame ───────────────────────────────────
    while True:
        fps.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                for sock in socks.values():
                    sock.close()
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN and not game_over:
                for dir_name, key in CONTROLS[1].items():
                    if event.key == key:
                        send_dir(socks[1], dir_name)
                for dir_name, key in CONTROLS[2].items():
                    if event.key == key:
                        send_dir(socks[2], dir_name)

        # Ambil state dari socket P1
        with lock:
            current_state = clients[1]['state']

        # ── Render ────────────────────────────────────────
        screen.fill(BLACK)

        # Grid
        for x in range(0, WIDTH, CELL):
            pygame.draw.line(screen, GRID_COL, (x, 0), (x, GRID_H * CELL))
        for y in range(0, GRID_H * CELL, CELL):
            pygame.draw.line(screen, GRID_COL, (0, y), (WIDTH, y))

        if current_state:
            stype = current_state.get('type')

            # Makanan — hanya tampil saat game berjalan
            food = current_state.get('food')
            if food and stype == 'state':
                cx = food['x'] * CELL + CELL // 2
                cy = food['y'] * CELL + CELL // 2
                pygame.draw.circle(screen, FOOD_COL, (cx, cy), CELL // 2 - 3)

            # Ular
            players_data = current_state.get('players', [])
            for p in players_data:
                snake = p.get('snake', [])
                if not snake:
                    continue
                c_head = GREEN if p['id'] == 1 else RED
                c_body = GREEN_DARK if p['id'] == 1 else RED_DARK
                for i, seg in enumerate(snake):
                    rect = pygame.Rect(seg['x']*CELL+1, seg['y']*CELL+1, CELL-2, CELL-2)
                    pygame.draw.rect(screen, c_head if i == 0 else c_body, rect, border_radius=6)

            # HUD
            hud_y = GRID_H * CELL
            pygame.draw.rect(screen, HUD_COL, (0, hud_y, WIDTH, 60))
            for p in players_data:
                pid   = p['id']
                alive = p['alive']
                ctrl  = "WASD" if pid == 1 else "Arrows"
                label = f"P{pid}[{ctrl}]: {p['score']} pts" + ("" if alive else " [MATI]")
                color = (GREEN if pid == 1 else RED) if alive else (100, 100, 100)
                x_pos = 20 if pid == 1 else WIDTH // 2 + 20
                screen.blit(font_hud.render(label, True, color), (x_pos, hud_y + 18))

            # Overlay
            def overlay(msg, sub=""):
                ov = pygame.Surface((WIDTH, GRID_H * CELL), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 160))
                screen.blit(ov, (0, 0))
                t1 = font_big.render(msg, True, WHITE)
                screen.blit(t1, t1.get_rect(center=(WIDTH//2, GRID_H*CELL//2 - 20)))
                if sub:
                    t2 = font_sm.render(sub, True, TEXT_COL)
                    screen.blit(t2, t2.get_rect(center=(WIDTH//2, GRID_H*CELL//2 + 24)))

            if stype == 'gameover':
                game_over = True
                winner = current_state.get('winner')
                winner_msg = "SERI!" if winner is None else (f"P{winner} MENANG!")
                overlay(winner_msg, "Tutup window untuk keluar")
            elif stype == 'countdown':
                overlay(str(current_state.get('count', '')), "Bersiap...")
            elif stype == 'start':
                overlay("GO!")

        else:
            # Belum ada state
            ov = pygame.Surface((WIDTH, GRID_H * CELL), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            screen.blit(ov, (0, 0))
            t1 = font_big.render("Menunggu...", True, WHITE)
            screen.blit(t1, t1.get_rect(center=(WIDTH//2, GRID_H*CELL//2)))

        pygame.display.flip()

if __name__ == '__main__':
    main()