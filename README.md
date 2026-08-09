<div align="center">

[![Buy me a coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/highfish)

```
 _     _    ___    _       _       _       _      _     __   __  ____  ____  _____
| |__ / \  |_ _|  | |__   (_) __ _| |__   / _|   | |  / /  / / |  _ \|___ \|_  /
| '_ \/ _ \  | |  | '_ \  | |/ _` | '_ \ | |_    | | / /  / /  | |_) | __) |/ /
| | | \___/ | |  | | | | | | (_| | | | | |  _|   | |/ /  / /  |  __/ / __// /_
|_| |_\___||___|  |_| |_| |_|\__, |_| |_| |_|     |_/_/  /_/   |_|   |_____/____|
                               |___/
        S A M B A   P L A Y E R   ·   H I G H F I S H   A I
```

**Deine 60.000 Tracks. Zuhause gehostet. Überall verfügbar.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PWA](https://img.shields.io/badge/PWA-Ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![Android](https://img.shields.io/badge/APK-PWABuilder-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://pwabuilder.com)
[![DietPi](https://img.shields.io/badge/DietPi-Debian-c5007d?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://dietpi.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Service Worker](https://img.shields.io/badge/Service_Worker-Offline_Ready-00C853?style=for-the-badge&logo=googlechrome&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
[![Auth](https://img.shields.io/badge/Auth-API_Key-FF5E3A?style=for-the-badge&logo=shield&logoColor=white)](#sicherheit)

---

> 🎵 **hAI.highfishMP3zPlayer** ist ein selbst gehosteter Musik-Streaming-Player von **Highfish AI**.  
> Läuft auf DietPi/Debian, indiziert bis zu **60.000 Tracks** in Sekunden,  
> und liefert sie als vollwertige **Progressive Web App** — inkl. **Android APK**.

</div>

---

## ✨ Features

| Feature | Details |
|---|---|
| 🗂 **Ordner-Browser** | Navigiere durch deine gesamte Musikbibliothek mit Breadcrumb |
| 🔍 **Globale Suche** | Serverseitige Volltextsuche über alle 60k Dateien in < 50ms |
| 🎵 **Streaming** | HTTP Range-Requests → Seek ohne Buffering |
| 🖼 **Album-Cover** | ID3-Tags (MP3/FLAC/M4A) oder `cover.jpg` im Ordner |
| 📋 **Queue** | Einzelne Tracks oder ganzen Ordner — Fisher-Yates Shuffle |
| 🔀 **Shuffle** | Zufällige Wiedergabe + Queue-Mischen per Knopfdruck |
| 🔁 **Repeat** | Aus / Einen Titel / Gesamte Queue |
| 🔐 **Login-Screen** | Passwortschutz mit Samba-Credentials als API-Key |
| 📱 **PWA + APK** | Service Worker, manifest.json, Lockscreen-Controls |
| 🔒 **Sicherheit** | Timing-Attack-sichere Auth via `secrets.compare_digest` |
| ⚡ **60k-ready** | Paginierung (80/Seite) + In-Memory-Index-Cache |
| 🌐 **CORS** | Zugriff via Cloudflare / eigener Domain |

---

## 🏗 Architektur

```
┌─────────────────────────────────────────────────────┐
│              Android APK / Browser / PWA             │
│                                                      │
│   ┌──────────────────────────────────────────────┐  │
│   │     samba-player.html  (Single File PWA)     │  │
│   │                                              │  │
│   │  🔐 Login  📁 Browse  🔍 Search  ▶ Player   │  │
│   │  🔀 Shuffle  🔁 Repeat  📋 Queue  🖼 Art    │  │
│   └────────────────────┬─────────────────────────┘  │
│                         │  SW cached / HTTP           │
└─────────────────────────┼───────────────────────────┘
                          │  Cloudflare / Fritzbox
          ┌───────────────▼──────────────┐
          │          DietPi / Debian      │
          │                               │
          │  ┌─────────────────────────┐  │
          │  │    mp3z_server.py       │  │
          │  │    Flask · dotenv Auth  │  │
          │  │                         │  │
          │  │  POST /api/verify       │  │
          │  │  GET  /api/browse       │  │
          │  │  GET  /api/search       │  │
          │  │  GET  /api/stream       │  │
          │  │  GET  /api/art          │  │
          │  └───────────┬─────────────┘  │
          │              │                │
          │  ┌───────────▼─────────────┐  │
          │  │  /mnt/USBHDD_MP3z       │  │
          │  │  60.000+ Audiodateien   │  │
          │  └─────────────────────────┘  │
          └───────────────────────────────┘
```

---

## 📂 Projektstruktur

```
hAI.highfishMP3zPlayer/
│
├── 🎵 samba-player.html     ← PWA Frontend (eine einzige Datei!)
├── 🐍 mp3z_server.py        ← Flask Backend
├── ⚙️  sw.js                 ← Service Worker (Offline + Caching)
├── 🔧 generate_icons.py     ← Icon-Generator (einmalig ausführen)
├── 📋 requirements.txt      ← Python-Abhängigkeiten
├── 🔑 .env.example          ← Konfigurationsvorlage (committet)
├── 🔒 .env                  ← Deine Zugangsdaten (NICHT committet!)
├── 🔧 systemd/
│   └── mp3z.service         ← systemd Unit-Datei
├── 📄 index.html            ← GitHub Pages Projektseite
├── 📜 LICENSE               ← MIT License
└── 📖 README.md             ← Diese Datei
```

> ⚠️ **`.env` niemals committen!** Sie ist in `.gitignore` eingetragen.

---

## 🚀 Installation

### Voraussetzungen

- 🐧 **Debian 11 Bullseye** oder **DietPi**
- 🐍 Python 3.9+
- 🌐 Domain mit DNS-Eintrag (Cloudflare empfohlen)
- 📂 Musiksammlung gemountet (z.B. `/mnt/USBHDD_MP3z`)

---

### Schritt 1 — Repo klonen

```bash
mkdir -p /opt/mp3z && cd /opt/mp3z
git clone https://github.com/therealteacher/hAI.highfishMP3zPlayer.git .
```

---

### Schritt 2 — Abhängigkeiten installieren

```bash
pip install -r requirements.txt --break-system-packages
```

---

### Schritt 3 — `.env` konfigurieren

```bash
cp .env.example .env
joe .env
```

Inhalt anpassen:

```ini
HOST=0.0.0.0
PORT=80
MUSIC_ROOT=/mnt/USBHDD_MP3z
SMB_USER=daniel              # ← dein Samba-Benutzername
SMB_PASS=deinSambaPasswort   # ← dein Samba-Passwort = API-Key
API_KEY_OVERRIDE=            # ← leer lassen
DEFAULT_URL=http://samba.arbeitermili.eu
```

---

### Schritt 4 — Icons generieren

```bash
python3 generate_icons.py
# → icon-192.png und icon-512.png werden erstellt
```

---

### Schritt 5 — Teststart

```bash
python3 mp3z_server.py
```

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🎵 hAI.highfishMP3zPlayer  v2.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  User      : daniel
  MusicRoot : /mnt/USBHDD_MP3z
  URL       : http://0.0.0.0:80
  API-Key   : ✓ gesetzt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Baue Datei-Index …
✓ Index: 61243 Dateien in 18.3s
```

---

### Schritt 6 — Autostart via systemd

```bash
cp systemd/mp3z.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable mp3z
systemctl start mp3z
systemctl status mp3z
```

---

### Schritt 7 — Docker / Portainer-Stack (alternativ zu systemd)

Das Repo baut automatisch ein **Docker-Image** via GitHub Actions und pusht es zu **GHCR** (`ghcr.io/jbkunama1/hai.highfishmp3zplayer_v2`).

**In Portainer deployen:**

1. **Environments → dein Server → Stacks → Add stack**
2. Name: `mp3z`
3. **Repository** auswählen:
   - Repository URL: `https://github.com/jbkunama1/hAI.highfishMP3zPlayer_V2`
   - Referenz: `main` (oder ein `vX.Y.Z`-Tag)
   - Compose-Pfad: `docker-compose.yml`
4. **Environment-Variablen** setzen:
   ```
   SMB_USER=daniel
   SMB_PASS=deinSambaPasswort
   DEFAULT_URL=http://samba.arbeitermili.eu
   ```
5. **Deploy the stack**

**Manuell via Docker:**
```bash
docker pull ghcr.io/jbkunama1/hai.highfishmp3zplayer_v2:latest
docker run -d --name mp3z -p 80:80 \
  -v /mnt/USBHDD_MP3z:/music:ro \
  -e SMB_USER=daniel -e SMB_PASS=deinSambaPasswort \
  ghcr.io/jbkunama1/hai.highfishmp3zplayer_v2:latest
```

> ⚠️ **Wichtig:** Die Musiksammlung muss als Volume gemountet sein (`/mnt/USBHDD_MP3z:/music:ro`). Das Image läuft als **Nicht-root-Benutzer** — bei gemounteten NTFS-Dateisystemen ggf. `user_uid`/`user_gid` am Mount setzen.

---

### Schritt 8 — Domain einrichten

```
Fritzbox Port-Forwarding:
  Extern 80 → DietPi-IP : 80

Cloudflare DNS:
  A-Record: samba.arbeitermili.eu → WAN-IP
  Proxy:    ☁ Proxied (kostenlos HTTPS!)
```

---

## 📱 Android APK erstellen

### PWABuilder (empfohlen, kostenlos)

```
1. https://pwabuilder.com aufrufen
2. URL eingeben: http://samba.arbeitermili.eu
3. "Start" → Score prüfen (sollte ≥ 80 sein)
4. "Android" → "Download Package"
5. APK auf Handy → Einstellungen → Unbekannte Quellen → Installieren
```

### Bubblewrap CLI

```bash
npm install -g @bubblewrap/cli
bubblewrap init --manifest http://samba.arbeitermili.eu/manifest.json
bubblewrap build
# → app-release-unsigned.apk
```

---

## 🔍 API Referenz

### Authentifizierung

Alle Endpoints außer `/api/verify` und `/api/client-config` benötigen den API-Key:

```
Header:    X-API-Key: deinPasswort
URL-Param: ?apikey=deinPasswort   (für stream/art)
```

### Endpoints

| Method | Endpoint | Auth | Beschreibung |
|--------|----------|------|---|
| `POST` | `/api/verify` | ✗ | Login — prüft API-Key |
| `GET`  | `/api/client-config` | ✗ | Öffentliche App-Konfiguration |
| `GET`  | `/api/browse` | ✓ | Paginiertes Verzeichnis-Listing |
| `GET`  | `/api/search` | ✓ | Globale Volltextsuche |
| `GET`  | `/api/stream` | ✓ | Audio-Streaming (Range-Requests) |
| `GET`  | `/api/art` | ✓ | Album-Cover |
| `GET`  | `/api/index-status` | ✓ | Index-Statistik |
| `GET`  | `/manifest.json` | ✗ | PWA Manifest |
| `GET`  | `/sw.js` | ✗ | Service Worker |
| `GET`  | `/icon-{192,512}.png` | ✗ | App-Icons |

---

## 🔒 Sicherheit

```ini
# .env
SMB_PASS=deinSambaPasswort   # = API-Key
```

- ✅ Timing-Attack-sicher via `secrets.compare_digest()`  
- ✅ SHA-256-Hash — Klartext-Passwort nie im Speicher verglichen  
- ✅ Directory-Traversal-Schutz via `Path.resolve()`  
- ✅ `.env` in `.gitignore` — Credentials niemals im Repo  
- ✅ HTTPS kostenlos via Cloudflare-Proxy empfohlen  

---

## ⚡ Performance

| Operation | Zeit |
|---|---|
| Index-Aufbau (60k Dateien) | ~15–30s (einmalig beim Start) |
| Suche nach Index-Build | < 50ms |
| Ordner laden (80 Einträge) | < 100ms |
| Album-Art (gecacht) | sofort (86400s Cache-Control) |
| Stream-Start | sofort (Range-Request) |

---

## 🗂 Unterstützte Formate

| Format | Streaming | Album-Art |
|--------|-----------|-----------|
| MP3  | ✅ | ✅ ID3 APIC |
| FLAC | ✅ | ✅ Picture Block |
| M4A  | ✅ | ✅ covr Atom |
| OGG  | ✅ | ⚠ cover.jpg |
| WAV  | ✅ | ⚠ cover.jpg |
| AAC  | ✅ | ✅ |
| OPUS | ✅ | ⚠ cover.jpg |
| WMA  | ✅ | ❌ |

---

## 🛠 Troubleshooting

**Port 80 belegt?**
```bash
# .env ändern:
PORT=8080
# Fritzbox: Extern 80 → Intern 8080
```

**Index baut nicht?**
```bash
ls -la /mnt/USBHDD_MP3z    # Mountpoint prüfen
df -h | grep USBHDD         # Mount prüfen
```

**Icons fehlen?**
```bash
python3 generate_icons.py
```

**Login schlägt fehl?**
```bash
curl -X POST http://localhost/api/verify \
  -H "Content-Type: application/json" \
  -d '{"apikey":"deinPasswort"}'
# Sollte: {"ok": true, "user": "daniel"}
```

**Service Worker aktualisieren?**
```bash
# Cache-Name in sw.js erhöhen:
const CACHE_NAME = 'mp3z-v2';  # war v1
```

---

## 👤 Autor

**TheRealTeacher** — Lehrer · IT-Professional · Maker · Highfish AI

[![GitHub](https://img.shields.io/badge/GitHub-therealteacher-181717?style=flat-square&logo=github)](https://github.com/therealteacher)
[![Highfish AI](https://img.shields.io/badge/Highfish-AI-ff5e3a?style=flat-square)](https://highfishai.de)
[![Instagram](https://img.shields.io/badge/Instagram-realteacher-E4405F?style=flat-square&logo=instagram)](https://instagram.com/realteacher)

---

## 📜 Lizenz

MIT License — mach damit was du willst, aber nenn die Quelle. 🤝

---

<div align="center">

**Made with 🎵 + ☕ + 🤖 by TheRealTeacher / Highfish AI**

*Self-hosted · Privacy-first · No cloud needed · 60k Tracks kein Problem*

</div>

