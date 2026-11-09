# Dauerhafte Betriebsstatistik

Aktiv im Startpfad `python cover_app.py`, auch bei deaktiviertem Telegram.
Die alten Minimalstarter binden dieses Zusatzmodul nicht ein.

## Container / Portainer

Die Hauptdatei docker-compose.yml bindet MP3Z_DATA_DIR (Standard:
/opt/mp3z-data) nach /data/mp3z ein und setzt MP3Z_STATS_PATH=/data/mp3z/stats.json.
Das Hostverzeichnis MUSS vor dem Deployment existieren und fuer PUID/PGID
(Standard 1000:1000) schreibbar sein. Beispiel auf dem Host:

```sh
sudo install -d -m 0750 -o 1000 -g 1000 /opt/mp3z-data
```

Bei anderen IDs/Pfaden entsprechend anpassen. Nicht als root betreiben und
keine Schreibrechte am Musikverzeichnis aendern. Andere Compose-/Portainer-
Varianten benoetigen denselben zusaetzlichen Mount und MP3Z_STATS_PATH.
Das bestehende Musik-Mount bleibt unveraendert. Fuer Native/systemd:
MP3Z_STATS_PATH auf eine dem Dienstbenutzer gehoerende Datei setzen;
Standard ist ~/.local/state/mp3z/stats.json. Dieses Verzeichnis sichern.

## Bedeutung und Grenzen

- Gesamtlaufzeit summiert nur laufende Sitzungen ab Installation dieses Features.
  Fruehere Laufzeiten/Indizierungen sind nicht rekonstruierbar; Ausfallzeit zaehlt nicht.
- Checkpoint alle 60 Sekunden und bei normalem Prozessende (atexit).
  Bei hartem Abbruch koennen bis zu 60 Sekunden ungesicherte Laufzeit fehlen,
  sofern die vorherigen Checkpoints erfolgreich waren.
- Starts und Indexversuche/Erfolge/Fehler werden gespeichert. Ein beim Absturz
  unterbrochener Versuch wird beim naechsten Start als Fehler verbucht.
- Letzter Index bedeutet letzter erfolgreich abgeschlossener Scan, nicht letzter Versuch.
  Fehlgeschlagene Scans ersetzen weder Eintraege noch gespeicherte Erfolgswerte.
- Dateianzahl und Groesse betreffen indizierte Audiodateien, nicht Cover oder Backups.
  GB = Bytes / 1.000.000.000. Eine nicht lesbare Dateigroesse macht die Gesamtgroesse unbekannt.
  Die Groessenabfrage erfolgt im Hintergrundscan, nicht beim Statusabruf; bei SMB
  bedeutet dies zusaetzliche Metadatenzugriffe pro Audiodatei.
- Nach Neustart wird der gespeicherte Stand getrennt vom frischen Live-Index angezeigt.
  Ein leerer erfolgreicher Scan ist 0 Dateien / 0 GB; fehlende Historie ist unbekannt.
- Nur ein Prozess darf die Statistikdatei schreiben (flock). Bei Konflikten oder
  Schreibfehlern laeuft der Player weiter, aber die Karten warnen vor fehlender Persistenz.
  Nach Behebung der Rechte ist ein Neustart erforderlich. Beschaedigte Daten werden
  einmalig als stats.json.corrupt aufbewahrt; Zaehler starten neu.
- Speicherung enthaelt nur aggregierte Werte, keine Dateipfade oder Zugangsdaten.

Tests: python -m unittest test_runtime_stats.py
