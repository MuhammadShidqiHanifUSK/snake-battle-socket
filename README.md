# 🐍 Snake Battle Socket

> Game multiplayer Snake berbasis jaringan menggunakan protokol **TCP Socket** dan **WebSocket**, dibuat untuk mata kuliah **Komunikasi Data** — Prodi Informatika, Universitas Syiah Kuala.

---

## 🎮 Tentang Game

**Snake Battle** adalah game dua pemain di mana masing-masing mengendalikan seekor ular di arena yang sama. Pemain berebut makanan untuk memanjangkan tubuh ularnya. Ular yang menabrak tembok, tubuh sendiri, atau tubuh lawan akan kalah. Game tersedia dalam dua versi: **desktop (pygame)** dan **web browser (WebSocket)**.

---

## ⚙️ Mekanik Game

| Aturan                  | Keterangan                              |
| ----------------------- | --------------------------------------- |
| 🍎 Makan makanan        | Badan ular bertambah panjang, skor +1   |
| 💀 Nabrak tembok        | Langsung kalah                          |
| 💀 Nabrak badan sendiri | Langsung kalah                          |
| 💀 Nabrak badan lawan   | Langsung kalah                          |
| 🏆 Kondisi menang       | Pemain yang masih hidup saat lawan mati |
| 🤝 Seri                 | Kedua ular mati di tick yang sama       |

---

## 🕹️ Kontrol

|             | Player 1                | Player 2 |
| ----------- | ----------------------- | -------- |
| **Atas**    | `W`                     | `↑`      |
| **Bawah**   | `S`                     | `↓`      |
| **Kiri**    | `A`                     | `←`      |
| **Kanan**   | `D`                     | `→`      |
| **Restart** | `R` (setelah game over) | `R`      |

---

## 🛠️ Tech Stack

| Komponen         | Teknologi                           |
| ---------------- | ----------------------------------- |
| Bahasa           | Python 3.11                         |
| Tampilan desktop | `pygame`                            |
| Jaringan desktop | TCP Socket (`socket` + `threading`) |
| Tampilan web     | HTML5 Canvas + CSS + JavaScript     |
| Jaringan web     | WebSocket (`websockets`)            |
| Format data      | JSON                                |

---

## 📁 Struktur Folder

```
snake-battle-socket/
│
├── server/
│   └── server.py         # Server TCP — game logic, broadcast state
│
├── client/
│   └── client.py         # Client pygame — render game, input handler
│
├── web/
│   ├── server_ws.py      # Server WebSocket untuk versi browser
│   ├── index.html        # Struktur halaman web
│   ├── style.css         # Tampilan UI web
│   └── game.js           # Logic game + koneksi WebSocket
│
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Instalasi

### 1. Clone repository

```bash
git clone https://github.com/MuhammadShidqiHanifUSK/snake-battle-socket.git
cd snake-battle-socket
```

### 2. Buat virtual environment (opsional tapi disarankan)

```bash
conda create -n snake-battle python=3.11
conda activate snake-battle
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Cara Menjalankan

### 🖥️ Versi Desktop (pygame)

**Terminal 1 — jalankan server:**

```bash
python server/server.py
```

**Terminal 2 — jalankan client:**

```bash
python client/client.py
```

Satu window akan terbuka untuk kedua pemain:

- 🟢 **Player 1** → kontrol `WASD`
- 🔴 **Player 2** → kontrol `↑↓←→`

> **Bermain via LAN (2 laptop):** Edit nilai `HOST` di `client/client.py` menjadi IP address laptop yang menjalankan server. Pastikan kedua laptop terhubung ke jaringan WiFi yang sama.

---

### 🌐 Versi Web (WebSocket)

**Terminal — jalankan WebSocket server:**

```bash
python web/server_ws.py
```

Buka file `web/index.html` di browser (double-click atau via Live Server VSCode).

> Pastikan server sudah berjalan sebelum membuka browser. Game akan otomatis reconnect jika koneksi terputus setelah game selesai.

---

## 🔄 Alur Komunikasi

```
[Client P1] ──── input (dir)  ────►┐
                                   │  [Server]
[Client P2] ──── input (dir)  ────►│  - Update posisi ular
                                   │  - Cek tabrakan
[Client P1] ◄─── game state  ──────┤  - Cek makan
                                   │  - Broadcast state
[Client P2] ◄─── game state  ──────┘
```

**Tipe pesan JSON:**

| Tipe        | Arah            | Keterangan                     |
| ----------- | --------------- | ------------------------------ |
| `init`      | Server → Client | Assign player ID + ukuran grid |
| `countdown` | Server → Client | Countdown sebelum game mulai   |
| `start`     | Server → Client | Game dimulai                   |
| `state`     | Server → Client | Posisi ular, makanan, skor     |
| `gameover`  | Server → Client | ID pemenang                    |
| `dir`       | Client → Server | Input arah gerak ular          |

---

## 👥 Anggota Kelompok

| Nama                  | NPM           |
| --------------------- | ------------- |
| Muhammad Shidqi Hanif | 2408107010096 |
| Muhammad Razi Siregar | 2408107010101 |
| Ahmad Hanif           | 2408107010114 |

---

## 📚 Mata Kuliah

**Komunikasi Data** — Prodi Informatika  
Universitas Syiah Kuala, 2026

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).
