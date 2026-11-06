# MCP-Auth und MP3-ID3-Editor

Docker startet metadata_app.py. Bestehende Backend- und Theme-Dateien bleiben erhalten. Neue Abhaengigkeiten stehen in requirements-metadata.txt.

## Portainer ENV

API_KEY_OVERRIDE ist jetzt Pflicht: eigener Web/API-Key, kein SMB_PASS-Fallback in diesem Startpfad. MCP_API_KEY ist ebenfalls Pflicht und sollte ein anderer zufaelliger ASCII-Key sein. Beide ohne Leerzeichen am Rand setzen. EDIT_ENABLED=false und MCP_WRITE_ENABLED=false sind sichere Standards. Fuer Web-Schreiben EDIT_ENABLED=true; fuer MCP-Schreiben zusaetzlich MCP_WRITE_ENABLED=true. STORAGE_MODE und alle bisherigen SMB-/lokalen Pfade bleiben bestehen. Musikvolume ist rw, passende Rechte auf Host/Share sind weiterhin erforderlich.

## Web

Im Player fuehrt der Link ID3-Editor nach /id3-editor. Zuerst im Player anmelden, relativen MP3-Pfad eingeben, laden, bearbeiten, speichern und bestaetigen. Titel, Artist, Album, Album-Artist, Track, Disc, Jahr und Genre sind verfuegbar. Leerer Feldwert entfernt dieses Feld. Kommentare und Cover werden nicht editiert und bleiben erhalten. Andere Dateiformate werden nicht geschrieben.

GET /api/id3?path=Artist/Album/Track.mp3 liest Tags und SHA256-Revision. POST /api/id3 erwartet JSON mit path, tags (nur gewuenschte Felder), revision. Beide brauchen X-API-Key. Schreibzugriff wird serverseitig geschuetzt. Fehler: 400 Validierung/alte Revision, 401 fehlender Key, 403 deaktiviert/keine Rechte, 404 fehlender Titel, 502 sonstiger Speicherfehler.

## MCP

Streamable HTTP: https://DEINE-DOMAIN/agent/mcp
Header: Authorization: Bearer DEIN_MCP_API_KEY

Tools: search_tracks (Dateinamen/Ordner mit offset/limit), read_id3 und update_id3. Die Auth-Middleware schuetzt auch Initialisierung und Tool-Listing, nicht nur Aufrufe. update_id3 erfordert beide Schreibflags und eine aktuelle Revision von read_id3. Der Agent/Client soll vor jedem Schreiben die Zustimmung des Nutzers einholen; es gibt keinen separaten serverseitigen Freigabedialog. Keine Rollenverwaltung pro Benutzer. Der alte separate mcp/mcp_server.py wird dadurch nicht automatisch abgesichert: diesen nicht parallel oeffentlich betreiben.

## Dateischutz

Einzelne Dateien bis 128 MiB. Sichtbare relative MP3-Pfade, keine Symlinks oder SMB-Reparse-Points. Ein Prozess-Lock und SHA256-Revision verhindern veraltete Aenderungen innerhalb dieses Prozesses. Fremde Programme/mehrere Replikate koennen weiterhin konkurrieren; nur eine schreibende Instanz betreiben. ID3v2.4 wird gespeichert; Audiobytes und andere Tags bleiben erhalten. Vor dem Ersetzen wird im selben Ordner .mp3z-UUID-Dateiname.bak angelegt. Backups werden nicht automatisch geloescht. Zum Restore Dienst stoppen und gewuenschtes Backup manuell auf den Originalpfad kopieren. Speicherplatz ueberwachen. SMB-Replace/ACL-Verhalten ist serverabhaengig und muss mit einer Kopie getestet werden.

## Pruefstatus

Lokale Unit-Tests pruefen ID3-Roundtrip, Audio-Sentinel, Cover-Erhalt, Backup, Schreibsperre, Pfad-/Symlinkschutz, Revision, Feldvalidierung und Bearer-Gate. Das sind keine echten Audio-Decoder-, Browser-, SMB-, Docker- oder MCP-Client-Handshake-Tests. Diese Integrationstests stehen aus. Vor Produktiveinsatz mit einer kleinen Kopie der Sammlung pruefen. Bestehende Stream-/Cover-URLs des Players verwenden weiterhin API-Keys in Queryparametern: HTTPS, vertrauenswuerdige Clients und keine Query-Logs am Proxy. Telegram und Cover-Upload sind nicht Teil dieses Schritts.
