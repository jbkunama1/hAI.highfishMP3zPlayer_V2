# Cover-Upload

Docker startet cover_app.py, einen Adapter um metadata_app.py. Er registriert Cover-Webrouten und MCP-Tools; bisherige ID3- und Theme-Funktionen bleiben bestehen. Pillow ist bereits in requirements.txt enthalten. Keine neuen ENVs: EDIT_ENABLED=true fuer Web-Schreiben; fuer MCP zusaetzlich MCP_WRITE_ENABLED=true. Web braucht X-API-Key, MCP den vorhandenen Bearer-Key auf /agent/mcp.

## Bedienung

Im ID3-Editor erscheint ein eigener Cover-Bereich mit Dateiauswahl und Vorschau. Embedded: relativen MP3-Pfad eingeben. Folder: vorhandenen relativen Ordner eingeben; leer bedeutet Musik-Root. Gespeichert wird fest cover.jpg, kein frei waehlbarer Dateiname. Vor dem Upload wird eine Revision geladen und das konkrete Ziel bestaetigt. Nach eingebetteter Bearbeitung vor weiteren ID3-Aenderungen Tags neu laden. Vorhandene andere Coverdateien werden nicht entfernt; eingebettete Cover haben im bestehenden Player Vorrang vor Ordner-Covern.

## REST/MCP

GET /api/cover-upload?path=...&target=embedded|folder liefert Revision. POST /api/cover-upload erwartet Multipart cover (Datei), path, target, revision. Eingebettetes Ziel braucht die aktuelle Dateirevision, Ordnerziel den Hash von cover.jpg oder missing bei noch nicht vorhandenem Cover. HTTP 400 bei Validierung/Revision, 401 ohne Key, 403 ohne Schreibfreigabe, 404 fehlendes Ziel, 413 zu grosser Request, 502 Speicherfehler.

MCP: inspect_cover(path,target) und upload_cover(path,image_base64,revision,target). Striktes Base64 und gleiche Bild-/Pfadvalidierung wie REST. Vor Agent-Schreibaktionen Zustimmung einholen; kein neuer serverseitiger Freigabedialog. Der bisherige separate MCP-Server im mcp-Ordner wird nicht erweitert.

## Schutz und Backups

JPEG, PNG oder WEBP, nur ein Frame, maximal 8 MiB und 16 Megapixel. Bild wird voll dekodiert, EXIF-Orientierung angewendet, Transparenz weiss hinterlegt und als JPEG mit maximal 1600x1600 gespeichert; Metadaten werden nicht uebernommen. Keine URL-Downloads. MP3-Frontcover (APIC Typ 3) werden ersetzt, andere APIC-Bilder und Tags bleiben erhalten. MP3-Ausgabe maximal 128 MiB. Lokaler und direkter SMB-Pfad verwenden den gemeinsamen Prozess-Lock mit dem ID3-Editor, Revisionspruefung und versteckte Backups .mp3z-UUID-Dateiname.bak vor dem Ersetzen. Keine automatische Backup-Bereinigung. Restore: Dienst stoppen, Backup manuell auf den Originalpfad kopieren. Fremde Writer und mehrere Instanzen sind nicht durch den Prozess-Lock geschuetzt; nur eine schreibende Instanz und vorerst Testkopien verwenden. SMB-Replace/ACL-Erhalt ist serverabhaengig.

Cover-API-Antworten erhalten no-store; bereits im Browser oder Service Worker gespeicherte Bilder koennen trotzdem einen Reload beziehungsweise Cache-Loeschen brauchen. Keine globale Cache-Loeschung implementiert.

## Testgrenzen

Sieben lokale Tests fuer Embedded-Cover, Titel-/Test-Audio-/Backcover-Erhalt, Backup, Ordner-Neuanlage/Ersetzen, defekte/zu grosse Bilder, Pixelgrenze, Schreibsperre, Revision, Pfade/Symlinks und einen dateisystembasierten SMB-Mock. Kein realer SMB-, Docker-, Browser-, REST- oder MCP-Handshake-Test; vor Produktivbetrieb pruefen. Kein Deployment ausgefuehrt. Telegram bleibt separat offen.
