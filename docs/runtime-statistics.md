# Betriebsstatistik in der vorhandenen SQLite-Datenbank

Der Startpfad `python cover_app.py` uebergibt exakt `lib.playlists.filename`
an die Statistik. Somit verwenden Playlists, Darstellungseinstellungen und
Betriebsstatistik dieselbe vorhandene `playlists.sqlite3`.
Die eigene Tabelle `mp3z_runtime_stats` speichert einen versionierten
Statistikdatensatz. Andere Tabellen werden weder ersetzt noch geloescht.
Es gibt keinen neuen Statistikordner, keinen zusaetzlichen Bind-Mount,
keine neue Datenbankdatei und keine separate JSON-/Lockdatei.
SQLite kann wie bisher temporaere Journal-/WAL-Dateien im Datenbankordner verwenden.

Vorhandene Datenbankfreigaben und Schreibrechte bleiben unveraendert.
Die Statistik hat dieselbe Persistenz wie diese SQLite-Datei: Ist deren
bisheriger Speicherort nicht persistent, ueberlebt auch sie keine
Container-Neuerstellung. Der separate Mount /opt/mp3z-data und
MP3Z_STATS_PATH aus der vorherigen Haupt-Compose-Version sind entfernt.
Bereits vorhandene benutzerdefinierte DB-Mounts im eigenen Stack beibehalten.

Optional: Falls die fruehere JSON-Statistik bereits benutzt wurde, kann
MP3Z_STATS_PATH einmalig auf die noch erreichbare alte JSON-Datei zeigen.
Sie wird nur importiert, wenn die SQLite-Statistiktabelle noch keinen Datensatz hat.
Die alte Datei bleibt unveraendert; danach ist diese Variable nicht mehr erforderlich.
Es wird niemals eine vorhandene SQLite-Datei als JSON umbenannt oder geloescht.

Gesamtlaufzeit zaehlt laufende Sitzungen ab Installation, keine Ausfallzeit.
Checkpoint alle 60 Sekunden und bei normalem Prozessende; bei hartem Abbruch
koennen seit dem letzten erfolgreichen Checkpoint bis zu 60 Sekunden fehlen.
Unterbrochene Indexversuche werden beim Neustart als Fehler gezaehlt.
Dateianzahl und GB (Bytes/1.000.000.000) beziehen sich auf Audiodateien des
letzten erfolgreichen Scans. Ein Fehler ersetzt diesen Stand nicht.
Fehlende Dateigroessen werden als unbekannt markiert. Die Groessenabfrage
erfolgt im Hintergrundscan; SMB benoetigt dafuer Metadatenzugriffe pro Datei.
Beide Telegram-Karten unterscheiden gespeicherten Stand und aktuelle Sitzung.

Nur ein Statistikschreiber pro DB (flock auf der bestehenden DB-Datei).
Normale SQLite-Transaktionen fuer Playlists bleiben moeglich. Bei fehlender
oder nicht schreibbarer DB laeuft die Statistik nur im Speicher und warnt;
nach Behebung ist ein Neustart erforderlich. Alte Minimalstarter ohne
cover_app binden dieses Zusatzmodul nicht ein. Vorherige Laufzeiten lassen
sich nicht rekonstruieren. Datenbank mit dem vorhandenen Backupverfahren sichern.

Tests: python -m unittest test_runtime_stats.py
