<div align="center">
<img src="icon-192.png" width="120" height="120" alt="MP3z Logo" />
<h1>hAI.highfishMP3zPlayer V2</h1>
<p>Deine Musiksammlung. Selbst gehostet. Im Browser, per MCP und Telegram.</p>
</div>

Musikplayer von TheRealTeacher / Highfish AI mit Ordnernavigation, Suche, Streaming, ID3-/Cover-Bearbeitung und optionalem Telegram-Admin-Cockpit. Die App verwendet genau eine Musikquelle: ein Host-Verzeichnis oder eine direkt angesprochene SMB-Freigabe.

## Inhalt

- [Funktionen](#funktionen)
- [Schnellstart mit Docker / Portainer](#schnellstart-mit-docker--portainer)
- [Musikquelle: Host oder SMB](#musikquelle-host-oder-smb)
- [Migration bestehender Installationen](#migration-bestehender-installationen)
- [Zugangsdaten und Schreibfreigaben](#zugangsdaten-und-schreibfreigaben)
- [MCP verbinden](#mcp-verbinden)
- [Telegram-Bot und Administration](#telegram-bot-und-administration)
- [Installation ohne Docker](#installation-ohne-docker)
- [HTTP-API](#http-api)
- [Tests und Fehlerbehebung](#tests-und-fehlerbehebung)

## Funktionen

| Bereich | Umfang |
|---|---|
| Bibliothek | Ordnernavigation, paginierte Einträge, Suche über Datei- und Ordnernamen |
| Wiedergabe | HTTP-Range-Streaming, Queue, Shuffle und Repeat im Webplayer |
| Cover | Eingebettete Cover und Bilddateien im Ordner; Cover-Bearbeitung |
| Metadaten | ID3-Editor; Schreiben nur mit entsprechender Freigabe |
| Oberfläche | Mobile Ansichten, Themes sowie Manifest und Service Worker für die PWA |
| Administration | Statusübersicht und Indexexport über die Admin-API |
| MCP | Bibliothek durchsuchen, Metadaten/Cover lesen und zeitlich begrenzte Streamlinks erzeugen |
| Telegram | Privates Inline-Cockpit, Suche, Statistik und bestätigungspflichtige Wartung |

Der Backend-Index liegt im Arbeitsspeicher. Es werden hier keine garantierten Track-Limits, Suchzeiten oder Offline-Audio-Funktionen zugesichert. Die Wiedergabe der Dateiformate hängt auch vom verwendeten Browser ab.

## Schnellstart mit Docker / Portainer

Repository: `https://github.com/jbkunama1/hAI.highfishMP3zPlayer_V2`

Image: `ghcr.io/jbkunama1/hai.highfishmp3zplayer_v2:latest`

1. In Portainer einen Repository-Stack mit diesem Repository und Referenz `main` anlegen.
2. Für Host-Speicher `docker-compose.yml` wählen. Für SMB ohne Host-Bind-Mount stattdessen `docker-compose.smb.yml` wählen. Die beiden Vorlagen nicht gemeinsam verwenden.
3. Das externe Docker-Netzwerk `highfishNetwork` muss auf dem Zielhost vorhanden sein. Falls es noch nicht existiert, vorher anlegen:

   ```bash
   docker network create highfishNetwork
   ```

4. Die benötigten Stack-Variablen eintragen. Beispiel für den Host-Modus:

   ```ini
   STORAGE_MODE=host
   MUSIC_ROOT=/mnt/USBHDD_MP3z/Audio
   HOST_PORT=8066
   PUID=1000
   PGID=1000
   APP_USERNAME=DEIN_APP_BENUTZER
   APP_PASSWORD=DEIN_EIGENES_APP_PASSWORT
   API_KEY_OVERRIDE=DEIN_SEPARATER_API_KEY
   MCP_API_KEY=DEIN_SEPARATER_MCP_KEY
   EDIT_ENABLED=false
   MCP_WRITE_ENABLED=false
   TELEGRAM_ENABLED=false
   ```

   Alle Zugangsdaten-Platzhalter durch eigene Werte ersetzen. Für Schlüssel beispielsweise `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` verwenden; API- und MCP-Key getrennt erzeugen. Geheimnisse nicht ins Repository übernehmen.

5. Stack bereitstellen. Der Container lauscht intern auf Port 80; Standard-Host-Port ist 8066. Webplayer: `http://DEINE_SERVER_IP:8066/`.

PUID und PGID müssen zu den Dateirechten auf deinem Host passen. Die Host-Vorlage bindet die Musikquelle beschreibbar ein; die App-Schreibfreigaben sind zusätzlich getrennt zu setzen.

Für CLI-Nutzung das Repository klonen, die Variablen in einer lokalen `.env` setzen und die passende Vorlage verwenden:

```bash
git clone https://github.com/jbkunama1/hAI.highfishMP3zPlayer_V2.git
cd hAI.highfishMP3zPlayer_V2
docker compose -f docker-compose.yml up -d
```

Ein Commit auf GitHub bestätigt noch keinen erfolgreichen Image-Build oder ein Deployment. Vor einem Update prüfen, ob das gewünschte Image tatsächlich bereitsteht.

## Musikquelle: Host oder SMB

### Host-Verzeichnis

```ini
STORAGE_MODE=host
MUSIC_ROOT=/mnt/USBHDD_MP3z/Audio
```

`MUSIC_ROOT` ist die einzige Host-Pfadvariable. `MUSIC_HOST_PATH` wird in der aktuellen Vorlage nicht mehr verwendet. Ohne `STORAGE_MODE` startet die normale App standardmäßig im Host-Modus; `local` bleibt als kompatibler Alias zulässig. In Statusanzeigen heißt dieser Backend-Modus weiterhin `local`.

Die Host-Compose-Vorlage verwendet denselben Pfad an allen drei Stellen:

```text
Host-Verzeichnis:  /mnt/USBHDD_MP3z/Audio
Container-Ziel:   /mnt/USBHDD_MP3z/Audio
App-MUSIC_ROOT:   /mnt/USBHDD_MP3z/Audio
```

Damit beginnt die Bibliothek beim Inhalt von `Audio`, nicht beim übergeordneten Datenträgerverzeichnis. Der Pfad muss absolut sein, existieren und für den Container-Benutzer lesbar sowie durchsuchbar sein. Die Vorlage setzt `create_host_path: false`: Ein falscher Pfad wird nicht als leeres Verzeichnis angelegt. Es gibt keinen automatischen Rückfall auf das Elternverzeichnis oder einen Standardordner.

### Direkte SMB-Quelle

Die eigenständige Vorlage `docker-compose.smb.yml` verwenden:

```ini
STORAGE_MODE=smb
SMB_HOST=DEIN_SMB_SERVER
SMB_SHARE=DEINE_FREIGABE
SMB_PATH=Audio
SMB_USER=DEIN_SMB_BENUTZER
SMB_PASS=DEIN_SMB_PASSWORT
SMB_PORT=445
SMB_DOMAIN=
SMB_ENCRYPT=false
```

`SMB_PATH` ist relativ zur Freigabe. Leer bedeutet ausdrücklich die Wurzel der Freigabe. SMB-Host, Freigabe, Benutzer und Passwort müssen gesetzt sein. Im SMB-Modus wird `MUSIC_ROOT` nicht als Musikquelle verwendet; fehlende SMB-Konfiguration führt nicht zum Wechsel auf Host-Speicher. Die SMB-Vorlage enthält keinen Host-Bind-Mount.

```bash
docker compose -f docker-compose.smb.yml up -d
```

`STORAGE_MODE` wählt die aktive App-Quelle per ENV, entfernt aber keine in Compose definierten Docker-Mounts. Wer die Host-Vorlage behält und dort `smb` setzt, behält einen ungenutzten Host-Mount und benötigt weiterhin deren `MUSIC_ROOT`-Variable. Für ein Deployment ohne diesen Mount ist die SMB-Vorlage erforderlich. Konfigurationswechsel benötigen eine Neuerstellung des Containers; es gibt kein Live-Umschalten.

Details: [Storage-Konfiguration](docs/STORAGE.md).

## Migration bestehender Installationen

**Ein Image-Update allein korrigiert keinen alten Mount.**

Bei bisherigen Installationen mit `/mnt/USBHDD_MP3z:/music` und festem `MUSIC_ROOT=/music`:

1. Die bisherige Stack-Konfiguration und die eigenen Variablen sichern; Geheimnisse nicht veröffentlichen.
2. Für den Host-Betrieb die aktuelle `docker-compose.yml` übernehmen.
3. `MUSIC_ROOT=/mnt/USBHDD_MP3z/Audio` als Stack-Variable setzen. Den alten Elternverzeichnis-Mount und die feste `/music`-Vorgabe nicht zusätzlich behalten.
4. Ein Image mit dem aktuellen Code bereitstellen und den Container mit der neuen Compose-Konfiguration neu erstellen.
5. Die Startlogs kontrollieren und die Bibliothek neu öffnen. Erwartet wird der Inhalt von `Audio`; `Video` und `lost+found` aus dem Elternverzeichnis sollen damit nicht als Root-Einträge erscheinen.

Beim Wechsel auf SMB stattdessen die SMB-Vorlage wählen und die SMB-Variablen setzen. Bestehende Telegram-Menübuttons und temporäre Streamlinks überleben einen Prozessneustart nicht; nach dem Update `/start` im Bot verwenden.

## Zugangsdaten und Schreibfreigaben

| Variable | Zweck |
|---|---|
| `APP_USERNAME`, `APP_PASSWORD` | Eigenständiger Webplayer-Login; unabhängig von SMB |
| `API_KEY_OVERRIDE` | Expliziter Schlüssel für die HTTP-API |
| `MCP_API_KEY` | Separater Bearer-Key für MCP |
| `SMB_USER`, `SMB_PASS` | Zugang zur SMB-Quelle, kein Ersatz für den App-Login |
| `EDIT_ENABLED` | Schreibfreigabe für Editor-Funktionen |
| `MCP_WRITE_ENABLED` | Zusätzliche Freigabe für MCP-Schreiboperationen |

Die vollständige App wird über `cover_app.py` gestartet und verlangt einen expliziten `API_KEY_OVERRIDE`. Alte Anleitungen, die `SMB_PASS` als App-Passwort/API-Key empfehlen oder den Override leer lassen, gelten dafür nicht mehr.

Der App-Login erstellt zeitlich begrenzte In-Memory-Sitzungen. Ein Neustart entfernt diese Sitzungen. Für Zugriff außerhalb eines vertrauenswürdigen lokalen Netzes HTTPS vorsehen; Schlüssel und Passwörter weder in öffentliche URLs noch in Screenshots oder Logs kopieren. Eine Host-Allowlist ersetzt keine Authentifizierung.

## MCP verbinden

Streamable-HTTP-Endpunkt:

```text
http://DEINE_SERVER_IP:8066/agent/mcp
```

Authentifizierung:

```text
Authorization: Bearer DEIN_SEPARATER_MCP_KEY
```

Der Client muss den Server erreichen können. Bei einem Tunnel oder Reverse Proxy die tatsächlich erreichbare URL verwenden.

### Invalid Host header

Der DNS-Rebinding-Schutz bleibt eingeschaltet. Den Host der verwendeten MCP-URL gezielt erlauben, beispielsweise für den LAN-Host dieser Installation:

```ini
MCP_ALLOWED_HOSTS=192.168.178.26:*
MCP_ALLOWED_ORIGINS=http://192.168.178.26:8066
```

Host-Einträge sind kommasepariert. `:*` erlaubt beliebige Ports dieses konkreten Hosts, nicht beliebige Hosts. Eine globale Host-Freigabe `*` wird von der Konfigurationsprüfung abgelehnt. Browser-Origins sind separat zu behandeln. Für eine eigene Domain oder einen Tunnel den passenden Host und gegebenenfalls die passende Origin ergänzen; den Schutz nicht pauschal abschalten.

Nach Konfigurationsänderungen den Container neu erstellen und im MCP-Client die Verbindung beziehungsweise Tool-Erkennung erneuern. Details: [MCP-Verbindung](docs/MCP-CONNECTION.md).

### Werkzeuge und Grenzen

Zu den Werkzeugen gehören `read_id3`, `update_id3`, `search_tracks`, `browse_library`, `library_status`, `read_cover` und `get_stream_link`. Schreiboperationen benötigen die passenden Freigaben; Metadatenänderungen verwenden eine zuvor gelesene Revision. Temporäre Streamlinks sind titelbezogene Freigaben mit zehn Minuten Laufzeit und sollten wie Zugangslinks behandelt werden.

## Telegram-Bot und Administration

Der Bot ist optional. Beispielvariablen:

```ini
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=DEIN_BOT_TOKEN
TELEGRAM_ALLOWED_USER_IDS=DEINE_NUMERISCHE_USER_ID
TELEGRAM_STATUS_CHAT_ID=DEINE_NUMERISCHE_USER_ID
TELEGRAM_STATUS_TIMEZONE=Europe/Berlin
PUBLIC_URL=
```

Mehrere erlaubte User-IDs werden kommasepariert angegeben. Für automatische Statusmeldungen muss `TELEGRAM_STATUS_CHAT_ID` genau eine erlaubte private User-ID sein. Ohne diese Variable bleiben automatische Meldungen aus. Bei Konfiguration sendet der Runtime-Bot eine Startmeldung nach HTTP-Bereitschaft und täglich um 22:00 Uhr in der gewählten Zeitzone einen Status.

`PUBLIC_URL` ist optional. Wenn gesetzt, muss sie eine HTTPS-Origin ohne Zugangsdaten, Query, Fragment oder zusätzlichen Pfad sein. Ohne sie entfällt der Webplayer-URL-Button; der Runtime-Bot kann trotzdem verwendet werden. Die automatische Statuskonfiguration zeigt nicht an, dass eine Zustellung tatsächlich erfolgreich war.

### Befehle und Inline-Cockpit

| Befehl | Funktion |
|---|---|
| `/start` | Musik-Cockpit mit Inline-Buttons |
| `/admin` | Wartungsmenü |
| `/status` | Bibliotheksstatus, Bot-Modullaufzeit und aktive temporäre Links |
| `/stats` | Titelzahl, Ordner mit indexierten Titeln und Dateiformate |
| `/settings` | Konfigurationsübersicht ohne Tokens, Passwörter oder Speicherpfade |
| `/browse` | Ordnernavigation |
| `/search Begriff` | Suche; alternativ einen Suchbegriff als Nachricht senden |
| `/help` | Hilfe |
| `/cancel` | Ausstehende Wartungsbestätigungen dieses Nutzers/Chats abbrechen |

Das Cockpit nutzt deutsche Texte mit Emojis. Es bietet Index-Neuaufbau, Sperren aller gespeicherten temporären Streamlinks und Deaktivieren alter Menübuttons im eigenen Chat. Der Neuaufbau wird im Hintergrund angestoßen; die Startbestätigung ist kein Nachweis eines erfolgreichen Abschlusses. Das Sperren der Links betrifft auch Freigaben anderer Nutzer, beendet aber bereits laufende Downloads nicht aktiv.

Der Bot akzeptiert nur freigegebene private Chats. Alle Nutzer aus `TELEGRAM_ALLOWED_USER_IDS` erhalten die Admin-Funktionen; getrennte Leser-/Adminrollen sind nicht implementiert. Wartungsbestätigungen sind an Nutzer und Chat gebunden, gelten 60 Sekunden und werden vor Ausführung verbraucht. Normale Menübuttons laufen nach zehn Minuten ab. Eine Fernsteuerung der Wiedergabe in einem bereits geöffneten Browser ist nicht enthalten.

## Installation ohne Docker

Für die vollständige Anwendung Python 3.11 wie im Docker-Image verwenden. Installation beispielsweise in einer virtuellen Umgebung:

```bash
git clone https://github.com/jbkunama1/hAI.highfishMP3zPlayer_V2.git
cd hAI.highfishMP3zPlayer_V2
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-metadata.txt
```

Eine lokale `.env` mit den App-/API-/MCP-Zugangsdaten und genau einer Storage-Konfiguration anlegen. Zusätzlich beispielsweise `HOST=0.0.0.0` und `PORT=8066` setzen. Danach:

```bash
python cover_app.py
```

Nicht `mp3z_server.py` als Ersatz für den vollständigen App-Start verwenden: Dieser ältere direkte Backend-Start aktiviert nicht alle Login-, Editor-, Admin-, Telegram- und Storage-Bootstrap-Erweiterungen. Bei systemd die vorhandene Unit vor Verwendung prüfen und Interpreter, Arbeitsverzeichnis, Benutzer sowie `ExecStart` auf die vollständige Anwendung anpassen; die ältere Unit nicht ungeprüft übernehmen.

## HTTP-API

Die folgenden Angaben beziehen sich auf den vollständigen Start über `cover_app.py`.

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/verify` | App-Login mit JSON-Feldern `username` und `password`; liefert Sitzungstoken |
| `POST` | `/api/logout` | Sitzungstoken aus `X-API-Key` widerrufen |
| `GET` | `/api/browse` | Ordner mit Pagination |
| `GET` | `/api/search` | Suche über den Index |
| `GET` | `/api/stream` | Audio-Streaming mit Range-Unterstützung |
| `GET` | `/api/art` | Cover lesen |
| `GET` | `/api/index-status` | Indexstatus |
| `GET`, `POST` | `/api/id3` | Metadaten lesen beziehungsweise mit Freigabe ändern |
| `GET` | `/api/admin/status` | Administrative Statusübersicht |
| `GET` | `/api/admin/export` | Indexexport, `format=json` oder `format=csv` |
| `GET` | `/api/ping` | HTTP-Bereitschaft; kein vollständiger Speichertest |

Geschützte HTTP-API-Aufrufe verwenden `X-API-Key` mit dem API-Key oder einem gültigen App-Sitzungstoken. MCP verwendet stattdessen seinen separaten Bearer-Key. Erfolgreicher Login oder `/api/ping` beweist nicht, dass eine SMB-Freigabe erreichbar ist.

## Tests und Fehlerbehebung

Nach Installation der Python-Abhängigkeiten können die gezielten Tests ohne echte Telegram-Aufrufe ausgeführt werden:

```bash
python -m unittest test_storage_config test_mcp_security test_telegram_admin test_app_login -v
```

Unit-Tests ersetzen keinen echten SMB-Verbindungstest, Image-Build oder Deploymenttest. Hier wird kein aktueller grüner CI-/Build-Status behauptet.

| Symptom | Prüfen |
|---|---|
| `Audio`, `Video`, `lost+found` als Root-Einträge | Alten Elternverzeichnis-Mount und feste `/music`-Vorgabe entfernen; aktuelle Host-Vorlage und exaktes `MUSIC_ROOT` verwenden |
| Host-Start scheitert | Existenz, absoluter Pfad, tatsächlicher Container-Mount und Lese-/Suchrechte des PUID/PGID-Benutzers |
| SMB-Konfiguration fehlt oder SMB nicht erreichbar | Modus, Host, Share, relative `SMB_PATH`, Zugangsdaten und Netzwerk prüfen; kein Host-Fallback erwarten |
| `Invalid Host header` bei MCP | Tatsächlich verwendeten Host in der MCP-Allowlist konfigurieren; Container neu erstellen und Tools neu erkennen |
| Web-Login schlägt fehl | `APP_USERNAME`/`APP_PASSWORD` statt SMB-Zugang verwenden |
| Telegram reagiert nicht | Aktivierung, Token, numerische Allowlist, privater Chat und Logs prüfen; nach Update `/start` senden |
| Keine automatischen Telegram-Meldungen | Erlaubte private `TELEGRAM_STATUS_CHAT_ID`, Zeitzone und Zustellfehler prüfen |
| Webplayer-Button fehlt | Optionale `PUBLIC_URL` als gültige HTTPS-Origin konfigurieren |
| Änderung nach GitHub-Push nicht sichtbar | Verfügbarkeit des richtigen Images sowie Stack-Konfiguration und Neuerstellung des Containers prüfen |

## Projektstruktur

```text
cover_app.py                Vollständiger App-Einstieg
storage_config.py           Exklusive Storage-Auswahl und Startprüfung
mp3z_server.py              Backend, Storage-Implementierungen und Dateiindex
metadata_app.py             HTTP-/MCP-App und ID3-API
metadata_service.py         Metadatenservice und MCP-Authentifizierung
cover_service.py            Cover-Funktionen
app_login.py                Eigenständiger App-Login und Sitzungen
library_tools.py            Gemeinsame Bibliotheksfunktionen und Streamlinks
telegram_bot.py             Basis-Bot und Telegram-Transport
telegram_admin.py           Inline-Cockpit und Wartung
telegram_runtime.py         Optionaler Bot-Start und Statusmeldungen
samba-player.html           Webplayer; Erweiterungen über Bootstrap-Dateien
docker-compose.yml          Host-Vorlage mit exakt MUSIC_ROOT
docker-compose.smb.yml      Eigenständige SMB-Vorlage ohne Host-Bind-Mount
docs/STORAGE.md             Storage-Details
docs/MCP-CONNECTION.md      MCP-Verbindungsdetails
```

## Autor und Lizenz

TheRealTeacher — Lehrer, IT-Professional, Maker / Highfish AI.

- [Originalautor auf GitHub](https://github.com/therealteacher)
- [Highfish AI](https://highfishai.de)
- [Instagram](https://instagram.com/realteacher)

MIT-Lizenz; siehe [LICENSE](LICENSE). Urheber- und Lizenzhinweise bei Weitergabe erhalten.
