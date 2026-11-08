# KI-Playlist-Assistent: Phase 1

Implementiert: Chat mit bis zu sechs Wunsch-/Korrekturschritten, serverseitiger
OpenAI-kompatibler Chat-Completions-Client, Bibliothekssuche, geprüfte Vorschau,
Speichern über den vorhandenen PlaylistStore und Queue-Übernahme im Browser.
Keine Live-Anfrage ohne Konfiguration. Kein Deployment durch diesen Commit.

## Konfiguration
AI_PLAYLIST_ENABLED=true
LLM_BASE_URL=https://9router.arbeitermili.eu/v1
LLM_MODEL=all_coding
LLM_API_KEY=<nur serverseitig als Umgebungsvariable hinterlegen>

Docker: docker-compose.ai.yml nach der bestehenden Compose-Datei und ggf.
docker-compose.playlists.yml hinzufügen. Das Image aus dem neuen Code bauen.
Der LLM-Key wird nicht im Browser gespeichert, nicht an REST-Clients ausgegeben
und nicht in den gemeinsamen Musikexport aufgenommen. Docker-Administratoren
können Umgebungsvariablen einsehen. Keine Zugangsdaten ins Repository committen.

## Bedienung
Button KI-Playlist öffnen, Wunsch eingeben und Zusammenstellen wählen.
Korrekturen beziehen sich auf den bisherigen Wunschverlauf und die letzte Auswahl.
Neue Unterhaltung startet ohne alten Kontext. Vorschauen leben maximal 30 Minuten
im Arbeitsspeicher; Container-Neustart verwirft sie. Gespeicherte Playlists bleiben
in der vorhandenen Datenbank. Speichern fragt den Namen ab; Queue-Ersetzen fragt nach.
Wiederholtes Speichern derselben Vorschau erzeugt nicht mehrere Playlists.
Alle Browser mit demselben API-Key gelten wie in der bestehenden Einzelkonto-App
als derselbe Akteur; Vorschau-IDs sind zufällige zusätzliche Zugriffstokens.

## Grenzen und Schutz
Phase 1 sucht Dateinamen/Ordner über Library.search, bis zu acht Suchbegriffe
mit je 50 Treffern. Das ist keine vollständige semantische ID3-Suche. Schlechte
Metadaten oder Suchpläne können passende Titel übersehen. Kein heimliches Auffüllen.
Bis zu 100 Titel, höchstens 500 Kandidaten, zwei gleichzeitige Generierungen,
30 Sekunden Timeout pro LLM-Aufruf, maximal 1 MiB Antwort. Zwei LLM-Aufrufe pro
Generierung: Suchplan und Auswahl. Keine automatischen kostenpflichtigen Retries.
Nur bekannte IDs werden akzeptiert, doppelte/fehlende Titel verworfen und gemeldet.
Stimmung, Sprache, Genre, Jahr und Dauer sind NICHT verifiziert. Die Oberfläche
zeigt das unabhängig vom Modelltext an. Exakte Dauer wird erst später ergänzt.
An den Anbieter gehen Nutzerwünsche sowie begrenzte Kandidaten-Dateinamen und
letzte Ordnernamen, keine Musikdateien, absoluten Pfade oder Speicherzugangsdaten.
HTTPS erforderlich; Redirects mit Bearer-Token werden nicht verfolgt. Nur der
Administrator kann Base-URL und Key konfigurieren. Keine LLM-Tools/Codeausführung.

REST: GET /api/ai-playlist zeigt enabled/configured. POST mit action=generate,
prompt und optional previous liefert eine Vorschau. POST action=save mit draft_id,
name und confirmed=true speichert exakt die serverseitige Auswahl.
Alle Datenendpunkte verlangen X-API-Key und liefern Cache-Control: no-store.
Frontend rendert LLM-Text mit textContent, nicht als HTML.

## Tests
python -m unittest test_ai_playlist -v
node --check ai-playlist.js
Die sechs Service-Tests nutzen simulierte LLM-/Such-/Speicheradapter. Beim lokalen
Lauf wurde auch der PlaylistStore-Vertrag simuliert, da das restliche Repository
nicht in der Laufzeitumgebung vorliegt. Kein echter Flask-/Browser-/Docker-/SMB-
oder all_coding-End-to-End-Test. Der echte LLM-Key wurde nicht bereitgestellt.

## Phase 2: nach Phase-1-Push
ID3-gestützte Metadatensuche und Filter (Genre, Sprache, Jahr), nachvollziehbare
Spieldauer, gespeicherte Wünsche, Telegram- und MCP-Assistent über denselben
Service. Sprache nur filtern, wenn Metadaten vorhanden sind; nichts als gemessen
behaupten, was nur geschätzt ist. Phase 2 ist mit diesem Commit NICHT implementiert.
