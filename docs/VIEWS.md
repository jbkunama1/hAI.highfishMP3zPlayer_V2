# Bibliotheksansichten

Fuenf Modi: Liste (Standard), Kompakt, Kacheln (mobil zwei Spalten, Desktop vier), Reihe (horizontal scrollbar) und Dropdown. Auswahl in eigener Leiste unter dem Suchfeld sowie im Verwaltungsmenue. Speicherung in localStorage unter mp3z_view, unabhaengig vom Theme.

Dropdown listet die aktuell geladenen Ordner-/Suchergebnisse. Auswahl alleine spielt nicht ab: Ordner oeffnen/Abspielen und Zur Queue sind explizite Aktionen. Queue ist fuer Ordner deaktiviert. Vorhandene Entry-Events werden genutzt; keine zweite Wiedergabe-/Queueimplementierung. Suche, Pagination und dynamisches Nachladen bleiben im alten Player. Die Darstellung aktualisiert sich per MutationObserver. Namen werden in Dropdown-Optionen als Text gesetzt, nicht als HTML.

Es werden nicht alle Dateien der Sammlung in ein riesiges Dropdown geladen. Mehr laden und Suche bleiben erforderlich. Leere-/Fehler-/Ladeanzeigen bleiben sichtbar. Bei Moduswechsel bleiben Player und Queue bestehen; die Auswahl im Dropdown kann bei Verzeichniswechsel zurueckgesetzt werden. Tastatur Enter/Leertaste auf fokussierten Eintraegen oeffnet/spielt ab; Select-Pfeiltasten werden nicht an globale Player-Shortcuts weitergeleitet.

Neue Dateien view_modes.py und view-modes.js, Einbindung im bestehenden cover_app.py. Keine neuen ENVs, keine Musikdatei-Aenderungen, kein Deployment durch den Assistenten. Node-Test prueft Modi/Fallback, Deduplizierung und Erhalt der Entry-Referenzen; Syntax ebenfalls geprueft. Echte DOM-/Touch-/Browser-/Screenreader- und Playbacktests stehen aus; CSS-Ansichten nicht als visuell verifiziert behaupten.
