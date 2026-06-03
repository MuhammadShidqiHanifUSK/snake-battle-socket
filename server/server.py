import socket
import threading
import json
import random
import time

# ─── Konfigurasi ───────────────────────────────────────────
HOST = '0.0.0.0'   # terima koneksi dari semua IP
PORT = 5555        # port yang dipakai
GRID_W = 30        # lebar arena (dalam kotak)
GRID_H = 25        # tinggi arena (dalam kotak)
TICK_RATE = 0.15   # kecepatan game (detik per tick)

# ─── State game ────────────────────────────────────────────
players = {}       # { conn: { 'id': int, 'snake': [...], 'dir': str, 'score': int, 'alive': bool } }
food = None        # posisi makanan { 'x': int, 'y': int }
game_running = False
lock = threading.Lock()

# ─── Fungsi bantu ──────────────────────────────────────────
def spawn_food():
    """Munculkan makanan di posisi acak yang tidak ditempati ular."""
    occupied = []
    for p in players.values():
        occupied += p['snake']
    while True:
        pos = {'x': random.randint(0, GRID_W - 1), 'y': random.randint(0, GRID_H - 1)}
        if pos not in occupied:
            return pos

def check_collision(snake, all_snakes):
    """Cek apakah kepala ular menabrak sesuatu."""
    head = snake[0]
    # Nabrak tembok
    if head['x'] < 0 or head['x'] >= GRID_W or head['y'] < 0 or head['y'] >= GRID_H:
        return True
    # Nabrak semua badan (termasuk diri sendiri)
    for s in all_snakes:
        if head in s[1:]:   # skip kepala lawan (boleh papasan kepala)
            return True
    return False

def move_snake(snake, direction):
    """Gerakkan ular 1 langkah sesuai arah, kembalikan posisi kepala baru."""
    head = snake[0].copy()
    if direction == 'UP':    head['y'] -= 1
    if direction == 'DOWN':  head['y'] += 1
    if direction == 'LEFT':  head['x'] -= 1
    if direction == 'RIGHT': head['x'] += 1
    return head

def broadcast(data):
    """Kirim data ke semua client yang terkoneksi."""
    msg = (json.dumps(data) + '\n').encode()
    dead = []
    for conn in list(players.keys()):
        try:
            conn.sendall(msg)
        except:
            dead.append(conn)
    for conn in dead:
        players.pop(conn, None)

# ─── Handle client ─────────────────────────────────────────
def handle_client(conn, addr, player_id):
    """Thread untuk menerima input dari 1 client."""
    global game_running
    print(f"[+] Player {player_id} terkoneksi dari {addr}")
    buffer = ''
    try:
        while True:
            data = conn.recv(1024).decode()
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
                    if msg.get('type') == 'dir':
                        with lock:
                            if conn in players and players[conn]['alive']:
                                new_dir = msg.get('dir')
                                cur_dir = players[conn]['dir']
                                # Cegah balik arah 180 derajat
                                opposites = {'UP':'DOWN','DOWN':'UP','LEFT':'RIGHT','RIGHT':'LEFT'}
                                if new_dir != opposites.get(cur_dir):
                                    players[conn]['dir'] = new_dir
                except:
                    pass
    except:
        pass
    finally:
        print(f"[-] Player {player_id} disconnect")
        with lock:
            if conn in players:
                players[conn]['alive'] = False
        conn.close()

# ─── Game loop ─────────────────────────────────────────────
def game_loop():
    """Loop utama: update posisi, cek tabrakan, broadcast state."""
    global food, game_running
    print("[*] Game loop dimulai!")

    while game_running:
        time.sleep(TICK_RATE)
        with lock:
            if len(players) < 2:
                continue

            all_snakes = [p['snake'] for p in players.values() if p['alive']]
            dead_this_tick = []

            for conn, p in players.items():
                if not p['alive']:
                    continue
                new_head = move_snake(p['snake'], p['dir'])
                p['snake'].insert(0, new_head)

                # Cek makan
                if new_head == food:
                    p['score'] += 1
                    food = spawn_food()
                else:
                    p['snake'].pop()  # hapus ekor kalau tidak makan

            # Cek tabrakan setelah semua ular bergerak
            all_snakes = [p['snake'] for p in players.values() if p['alive']]
            for conn, p in players.items():
                if not p['alive']:
                    continue
                other_snakes = [p2['snake'] for c2, p2 in players.items() if c2 != conn and p2['alive']]
                if check_collision(p['snake'], other_snakes + [p['snake']]):
                    dead_this_tick.append(conn)

            for conn in dead_this_tick:
                players[conn]['alive'] = False

            # Bangun state untuk dikirim ke client
            state = {
                'type': 'state',
                'food': food,
                'players': [
                    {
                        'id': p['id'],
                        'snake': p['snake'],
                        'score': p['score'],
                        'alive': p['alive']
                    }
                    for p in players.values()
                ]
            }
            broadcast(state)

            # Cek kondisi game over
            alive_players = [p for p in players.values() if p['alive']]
            if len(alive_players) <= 1:
                # Tentukan pemenang
                if alive_players:
                    winner_id = alive_players[0]['id']
                else:
                    winner_id = None  # seri (mati barengan)

                broadcast({'type': 'gameover', 'winner': winner_id})
                game_running = False
                print(f"[*] Game selesai! Pemenang: Player {winner_id}")
                break

    print("[*] Game loop berhenti.")

# ─── Main server ───────────────────────────────────────────
def start_server():
    global food, game_running

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)
    print(f"[*] Server berjalan di {HOST}:{PORT}")
    print("[*] Menunggu 2 pemain...")

    player_id = 1
    while len(players) < 2:
        conn, addr = server.accept()

        # Tentukan posisi awal ular (kiri dan kanan)
        # Player 1 — pojok kiri
        if player_id == 1:
            start_snake = [{'x': 2, 'y': 5}, {'x': 1, 'y': 5}, {'x': 0, 'y': 5}]
            start_dir = 'RIGHT'
        # Player 2 — pojok kanan
        else:
            start_snake = [{'x': 17, 'y': 14}, {'x': 18, 'y': 14}, {'x': 19, 'y': 14}]
            start_dir = 'LEFT'

        with lock:
            players[conn] = {
                'id': player_id,
                'snake': start_snake,
                'dir': start_dir,
                'score': 0,
                'alive': True
            }

        # Beritahu client nomor player mereka
        conn.sendall((json.dumps({'type': 'init', 'player_id': player_id}) + '\n').encode())

        t = threading.Thread(target=handle_client, args=(conn, addr, player_id), daemon=True)
        t.start()

        player_id += 1

    print("[*] 2 pemain terkoneksi! Game dimulai dalam 3 detik...")
    food = spawn_food()
    # Countdown 6-5-4-3-2-1
    for i in range(6, 0, -1):
        broadcast({'type': 'countdown', 'count': i, 'food': food})
        time.sleep(1)

    game_running = True
    broadcast({'type': 'start', 'food': food})

    game_loop()
    server.close()

if __name__ == '__main__':
    start_server()