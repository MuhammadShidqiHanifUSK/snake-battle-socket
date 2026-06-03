import asyncio
import websockets
import json
import random

# ─── Konfigurasi ───────────────────────────────────────────
HOST      = 'localhost'
PORT      = 8765
GRID_W    = 30
GRID_H    = 25
TICK_RATE = 0.15

# ─── State game ────────────────────────────────────────────
players    = {}   # { ws: { 'id': int, 'snake': [...], 'dir': str, 'score': int, 'alive': bool } }
food       = None
game_running = False
connected  = []   # list websocket yang terkonek

# ─── Fungsi bantu ──────────────────────────────────────────
def spawn_food():
    occupied = []
    for p in players.values():
        occupied += p['snake']
    while True:
        pos = {'x': random.randint(0, GRID_W - 1), 'y': random.randint(0, GRID_H - 1)}
        if pos not in occupied:
            return pos

def check_collision(snake, all_snakes):
    head = snake[0]
    if head['x'] < 0 or head['x'] >= GRID_W or head['y'] < 0 or head['y'] >= GRID_H:
        return True
    for s in all_snakes:
        if head in s[1:]:
            return True
    return False

def move_snake(snake, direction):
    head = snake[0].copy()
    if direction == 'UP':    head['y'] -= 1
    if direction == 'DOWN':  head['y'] += 1
    if direction == 'LEFT':  head['x'] -= 1
    if direction == 'RIGHT': head['x'] += 1
    return head

async def broadcast(data):
    msg = json.dumps(data)
    dead = []
    for ws in list(connected):
        try:
            await ws.send(msg)
        except:
            dead.append(ws)
    for ws in dead:
        if ws in connected:
            connected.remove(ws)

# ─── Game loop ─────────────────────────────────────────────
async def game_loop():
    global food, game_running
    print("[*] Game loop dimulai!")

    while game_running:
        await asyncio.sleep(TICK_RATE)

        if len(players) < 2:
            continue

        # Gerakkan semua ular
        for ws, p in list(players.items()):
            if not p['alive']:
                continue
            new_head = move_snake(p['snake'], p['dir'])
            p['snake'].insert(0, new_head)

            if new_head == food:
                p['score'] += 1
                food = spawn_food()
            else:
                p['snake'].pop()

        # Cek tabrakan
        dead_this_tick = []
        for ws, p in list(players.items()):
            if not p['alive']:
                continue
            other_snakes = [p2['snake'] for ws2, p2 in players.items() if ws2 != ws and p2['alive']]
            if check_collision(p['snake'], other_snakes + [p['snake']]):
                dead_this_tick.append(ws)

        for ws in dead_this_tick:
            if ws in players:
                players[ws]['alive'] = False

        # Broadcast state
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
        await broadcast(state)

        # Cek game over
        alive = [p for p in players.values() if p['alive']]
        if len(alive) <= 1:
            winner_id = alive[0]['id'] if alive else None
            await broadcast({'type': 'gameover', 'winner': winner_id})
            game_running = False
            print(f"[*] Game selesai! Pemenang: Player {winner_id}")
            break

    print("[*] Game loop berhenti.")

# ─── Handle koneksi WebSocket ──────────────────────────────
async def handle_connection(ws):
    global food, game_running

    if len(players) >= 2:
        await ws.send(json.dumps({'type': 'error', 'msg': 'Server penuh (max 2 pemain)'}))
        return

    player_id = len(players) + 1
    connected.append(ws)

    if player_id == 1:
        start_snake = [{'x': 2, 'y': 5}, {'x': 1, 'y': 5}, {'x': 0, 'y': 5}]
        start_dir   = 'RIGHT'
    else:
        start_snake = [{'x': 27, 'y': 19}, {'x': 28, 'y': 19}, {'x': 29, 'y': 19}]
        start_dir   = 'LEFT'

    players[ws] = {
        'id':    player_id,
        'snake': start_snake,
        'dir':   start_dir,
        'score': 0,
        'alive': True
    }

    await ws.send(json.dumps({'type': 'init', 'player_id': player_id, 'grid_w': GRID_W, 'grid_h': GRID_H}))
    print(f"[+] Player {player_id} konek")

    # Jika sudah 2 player, mulai game
    if len(players) == 2:
        print("[*] 2 pemain terkonek! Memulai countdown...")
        food = spawn_food()
        for i in range(6, 0, -1):
            await broadcast({'type': 'countdown', 'count': i, 'food': food})
            await asyncio.sleep(1)
        game_running = True
        await broadcast({'type': 'start', 'food': food})
        asyncio.create_task(game_loop())

    # Terima input dari client
    try:
        async for message in ws:
            try:
                msg = json.loads(message)
                if msg.get('type') == 'dir' and ws in players:
                    p = players[ws]
                    if p['alive']:
                        new_dir = msg.get('dir')
                        cur_dir = p['dir']
                        opposites = {'UP':'DOWN','DOWN':'UP','LEFT':'RIGHT','RIGHT':'LEFT'}
                        if new_dir != opposites.get(cur_dir):
                            p['dir'] = new_dir
            except:
                pass
    except:
        pass
    finally:
        print(f"[-] Player {player_id} disconnect")
        if ws in players:
            players[ws]['alive'] = False
        if ws in connected:
            connected.remove(ws)

# ─── Main ──────────────────────────────────────────────────
async def main():
    print(f"[*] WebSocket server berjalan di ws://{HOST}:{PORT}")
    print("[*] Buka index.html di browser untuk bermain")
    async with websockets.serve(handle_connection, HOST, PORT):
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())