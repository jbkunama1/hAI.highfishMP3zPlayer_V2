# MCP Server — MP3z Musikbibliothek

`mcp_server.py` macht die MP3z-Musikbibliothek über das **Model Context Protocol (MCP)** für MCP-Clients verfügbar (Claude Desktop, Copilot, …). Clients können die Sammlung durchsuchen, Track-Metadaten abfragen und Download-/Stream-Links erhalten.

## Tools

| Tool               | Beschreibung                                            | Rückgabe                                                      |
|--------------------|---------------------------------------------------------|---------------------------------------------------------------|
| `search_tracks(query, limit)` | Suche in Dateinamen und Ordnern (min. 2 Zeichen) | `{name, path, source, dir}`                                  |
| `get_track_info(path)`  | Metadaten eines Tracks via mutagen          | Titel, Künstler, Album, Dauer, Größe, Format                  |
| `get_stream_url(path)` | Download-/Stream-URL über den MP3z-Endpoint | `{path, url, description}`                                   |
| `get_browse(path='')`  | Verzeichnislisting (Ordner, Audio, Coverart) | `{type, name, path, size}`                                   |

## Installation

```bash
cd mcp
python -m venv .venv && .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Konfiguration (Umgebungsvariablen)

| Variable | Default | Bedeutung |
|---|---|---|
| `MUSIC_ROOT` | ungesetzt | Musikwurzel **Lokaler Modus** |
| `MUSIC_ROOTS` | ungesetzt | Multi-Root: JSON `{"usb": "/mnt/HDD", "nas": "/srv/musik"}` oder Liste `["/a", "/b"]` |
| `MP3Z_BASE_URL` | ungesetzt | **HTTP-Modus**: Basis-URL des MP3z-Servers (z. B. `http://mp3z:8066`) |
| `MP3Z_STREAM_BASE` | `MP3Z_BASE_URL` | Basis-URL für lokale Streams (falls Streaming-URL nicht `/api/stream` am MP3z-Server folgt) |
| `MP3Z_API_KEY` | `API_KEY_OVERRIDE` / `SMB_PASS` | API-Key für den MP3z-Server (nicht gehärtet, nur env) |
| `MCP_DISPLAY_NAME` | `mp3z` | Anzeigename des MCP-Servers |

**Moduswahl:** `MP3Z_BASE_URL` gesetzt → HTTP-Modus (funktioniert remote, nutzt `/api/search`, `/api/browse`, `/api/stream`). Sonst lokaler Modus (direkter Dateisystem-Zugriff, schneller, mit Pfad-Traversal-Schutz).

### Multi-Root-Pfade

Im lokalen Modus bekommen Pfade ein Quellen-Präfix: `usb/Album/01 Titel.mp3`, `nas/Playlist …`. `default` ist die `MUSIC_ROOT`-Wurzel und erscheint **ohne** Präfix.

`get_browse('')` ohne `default`-Wurzel (nur `MUSIC_ROOTS`) listet die konfigurierten Roots als Verzeichnis-Einträge, damit Clients `usb`, `nas`, … entdecken können.

## Start

```bash
# stdio (Standard, für MCP-Client-Konfiguration)
python mcp_server.py

# Streamable HTTP
python mcp_server.py --http --port 8080
```

Der Server läuft mit `FastMCP` (mcp-SDK); das `--http`-Flag aktiviert den streamable-HTTP-Transport gemäß MCP-Spezifikation.

## Client-Konfiguration

Claude Desktop — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mp3z": {
      "command": "python",
      "args": ["/pfad/zu/mcp/mcp_server.py"],
      "env": {
        "MUSIC_ROOT": "/mnt/USBHDD_MP3z",
        "MP3Z_API_KEY": "dein-api-key",
        "MP3Z_STREAM_BASE": "http://mp3z:8066"
      }
    }
  }
}
```

**HTTP-Modus-Client** (z. B. MCP-Client mit URL-Unterstützung):

```
http://localhost:8080/mcp
```

## Sicherheit

- API-Key/Passwort ausschließlich über Umgebungsvariablen — keine Hardcodierung.
- Lokaler Modus: `safe_local_path()` lehnt `..`, `…/..` und führende Punkte ab; aufgelöste Pfade müssen innerhalb der konfigurierten Musikwurzel liegen (mehrstufige Absicherung).

## Selftest

```bash
python mcp_server.py --selftest --music-root ./sample_music
# → SELFTEST OK: search_tracks, get_track_info, get_stream_url, get_browse, traversal-protection

# gegen laufenden MP3z-Server (HTTP-Modus):
python mcp_server.py --selftest --http-url http://localhost:8066 --http-key dein-key
```

## Docker

```bash
docker build -t mp3z-mcp ./mcp
# stdio (auf Host):
docker run --rm -v /mnt/USBHDD_MP3z:/music -e MUSIC_ROOT=/music mp3z-mcp
# streamable HTTP:
docker run --rm -p 8080:8000 -e MUSIC_ROOT=/music mp3z-mcp --http --port 8000
```