# Genau eine Musikquelle

Diese Konfiguration gilt fuer den normalen App-Start ueber cover_app.py (Docker-CMD). STORAGE_MODE=host verwendet nur MUSIC_ROOT. local bleibt als Alias kompatibel. Ohne STORAGE_MODE ist host der Standard. STORAGE_MODE=smb verwendet nur die SMB-Konfiguration; MUSIC_ROOT wird fuer die App deaktiviert. Kein automatischer Wechsel und kein Rueckfall auf ein Elternverzeichnis bei Fehlern. Die Backend-Statusanzeige nennt den Host-Modus weiterhin local.

## Host

Portainer-Stackvariable:

```ini
STORAGE_MODE=host
MUSIC_ROOT=/mnt/USBHDD_MP3z/Audio
```

STORAGE_MODE kann fuer den Host-Standard entfallen. Die aktualisierte docker-compose.yml verwendet MUSIC_ROOT sowohl als Host-Bind-Quelle als auch als Container-Ziel und App-Wurzel. MUSIC_HOST_PATH wird nicht mehr verwendet. Nur das exakt angegebene Verzeichnis wird eingebunden; der bisherige Mount des Elternverzeichnisses nach /music muss durch diese Vorlage ersetzt werden. Fehlendes Verzeichnis wird nicht automatisch erstellt (create_host_path: false); fehlende Leserechte fuehren zum Startfehler. Auch ausserhalb von Docker muss MUSIC_ROOT existieren und lesbar sein.

## SMB

```ini
STORAGE_MODE=smb
SMB_HOST=DEIN_SMB_SERVER
SMB_SHARE=DEINE_FREIGABE
SMB_PATH=Audio
SMB_USER=DEIN_BENUTZER
SMB_PASS=DEIN_PASSWORT
SMB_PORT=445
```

SMB_PATH ist relativ zur Freigabe; leer bedeutet ausdruecklich Freigabe-Wurzel. Fuer ein SMB-Deployment ohne jeden Host-Bind-Mount die eigenstaendige docker-compose.smb.yml anstelle der Host-Vorlage verwenden, nicht beide zusammenfuehren. Beispielsweise per CLI `docker compose -f docker-compose.smb.yml up -d`; in Portainer diese Datei als Stack-Vorlage waehlen. Zugangsdaten nicht committen.

STORAGE_MODE schaltet die aktive App-Quelle per ENV um. Docker-Mounts aendern sich dadurch nicht bedingt: Wer die Host-Compose-Datei behaelt und dort auf smb schaltet, behaelt einen ungenutzten Host-Mount und muss weiterhin MUSIC_ROOT fuer diese Vorlage setzen. Fuer wirklich keinen Host-Mount ist die SMB-Vorlage erforderlich. Nach Aenderungen Container neu erstellen; kein Live-Umschalten im laufenden Prozess. Web-, MCP- und Telegram-Funktionen verwenden dieselbe ausgewaehlte Storage-Instanz.

Tests: `python -m unittest test_storage_config -v`. Kein echtes SMB-/Portainer-Deployment in den Unit-Tests.
