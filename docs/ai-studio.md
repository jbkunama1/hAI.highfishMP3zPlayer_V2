# Phase 2b: KI Mix Studio

Webdialog: explizite Genre-/Sprach-/Jahresfilter, Chat-Nachbesserung, Vorschau,
Queue-Übernahme, Playlist speichern, Wünsche erstellen/laden/löschen.
Vorlagen lösen beim Laden keine LLM-Anfrage aus. Speichern/Löschen braucht
Bestätigung. Chat-Vorlagen speichern den zusammengeführten Wunschtext (max. 2000
Zeichen), nicht sämtliche Zwischenantworten. Musikdateien bleiben unverändert.

Wünsche liegen in ai-wishes.sqlite3 neben playlists.sqlite3. Persistenz benötigt
weiterhin ein beschreibbares Datenvolume. Maximal 100 Wünsche je Akteur, 1000 gesamt.
Web-Akteur: Hash des Anwendungs-API-Keys. Telegram: Benutzer plus privater Chat.
MCP: ein gemeinsamer vertrauenswürdiger Account. Vorlagen werden nicht automatisch
zwischen diesen Bereichen geteilt. Alle Browser mit gleichem Key teilen Vorlagen.
Vorlagen/Katalog sind noch nicht im gemeinsamen Index-/Playlist-Export enthalten.

Zusätzliche optionale Freigaben in docker-compose.ai.yml:
MCP_AI_ENABLED=true
TELEGRAM_AI_ENABLED=true
Schreiben über diese Kanäle benötigt weiterhin MCP_PLAYLIST_WRITE_ENABLED bzw.
TELEGRAM_PLAYLIST_WRITE_ENABLED. Alle Flags sind standardmäßig false.
AI_PLAYLIST_ENABLED, LLM_BASE_URL, LLM_MODEL und serverseitiger LLM_API_KEY aus
Phase 1 bleiben erforderlich. Kein Key wird eingecheckt. Kein Deployment enthalten.

MCP: ai_playlist_assistant(action, options_json, approved, confirmed).
Aktionen: generate/get/save/wish_list/wish_get/wish_create/wish_delete.
options_json enthält prompt/filters/previous oder draft_id/name bzw. id.
Generate erfordert approved=true für Kosten und Datenübertragung zum LLM.
Schreibaktionen benötigen confirmed=true und separate Schreibfreigabe.
Der Server vertraut darauf, dass der MCP-Client echte Nutzerfreigaben einholt;
Bool-Parameter sind keine kryptografischen Freigabenachweise.

Telegram (nur Allowlist und private Chats):
/mix Wunsch: neue Vorschau
/mixmore Korrektur: letzte Vorschau nachbessern
/mixnew: Unterhaltung zurücksetzen
/mixwishes: erste 25 gespeicherte Wünsche mit ID
/mixuse ID: Vorlage verwenden (führt LLM-Anfrage aus)
/mixwish Name: aktuellen Wunsch nach Bestätigung merken
Vorschau zeigt zehn Titel pro Seite. Playlist-Speichern hat eine zweite,
einmalige, 60 Sekunden gültige Bestätigung. Keine Fernsteuerung offener Browser.
Generierung läuft synchron und kann die Bot-Verarbeitung während der zwei
begrenzten LLM-Aufrufe vorübergehend verzögern. Kein automatischer Retry.

REST: /api/ai-studio, gleicher X-API-Key wie bestehende App, Cache-Control no-store.
GET meldet enabled/configured. POST verwendet dieselben Aktionen wie MCP mit
JSON-Feldern und confirmed=true für Änderungen.

Prüfung: python -m unittest test_ai_studio -v; node --check ai-playlist.js.
Fünf Offline-Tests mit echten temporären SQLite-Dateien; LLM, Flask und Telegram
werden simuliert. Kein Browser-/Docker-/SMB-/Live-LLM-End-to-End-Test.
Bestehende Phase-2a-Grenzen bleiben: Filter sind nur so gut wie die gescannten
MP3-Tags; fehlende Dauer wird ausgewiesen. Keine exakte Zieldauer-Optimierung.
