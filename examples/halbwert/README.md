# HALBWERT — Beispielseite der Scrollcraft-Skill

Eine vollständige Seite, gebaut mit `skills/scrollcraft/`, um die Skill an einem echten Fall zu
testen. Sie hat drei Aufgaben: zeigen, wie das Ergebnis aussehen soll, den Scroll-Score an einem
ausgeführten Beispiel belegen, und als Regressionsfall für die Scroll-Engine dienen.

**HALBWERT ist ein erfundenes Studio.** Alle Zahlen, Termine, Systemnamen und die Adresse sind
Platzhalter ohne Beleg. Die Seite weist das selbst aus — in der Kopfzeile und im Footer. Wer sie
als Vorlage nimmt, ersetzt diese Werte, statt sie mitzuschleppen.

## Ansehen

```bash
python -m http.server 8000     # in diesem Ordner
```

Dann scrollen — langsam einmal durch, schnell zurück, und einmal auf halber Höhe neu laden.

## Was hier zu sehen ist

| Szene | Mechanik |
|---|---|
| Hero | Systemliste erlischt, `track()` mit `startAtRest`, damit im Ruhezustand nichts vorgespielt ist |
| Exhibit 01 — Cutover | gepinnte Szene: Uhr, zwei Verkehrsbalken, Rollback-Fenster und Protokoll an einem Fortschritt |
| Exhibit 02 — Rückstand | Feldwechsel nach dunkel, danach drei gebundene Zähler mit unterschiedlichem Gewicht |
| Methode | Horizontal-Rail auf dem Desktop, Swipe-Strip auf dem Telefon |
| Grenzen | Feldwechsel zurück aufs Papier, gestaffelte Reveals, Marginalie |

`SCROLL-SCORE.md` ist der Plan, der vor dem Code entstand — Szene für Szene mit Behauptung,
Mechanik, Scroll-Kosten und Tonlage. Er ist Teil des Beispiels: die Skill verlangt ihn, bevor
eine Zeile HTML geschrieben wird.

Drei Muster hier sind aus Fehlern entstanden, die erst beim Bauen sichtbar wurden, und stehen
deshalb auch in den Referenzen der Skill:

- Auf dem Telefon ist die Szene nicht mehr gepinnt, also liefert `pin()` keinen Fortschritt mehr.
  Dieselben Callbacks laufen dort über `track()` (`bind = phone ? track : pin`).
- Instrumentenleiste und `--field` werden von mehreren Szenen beschrieben. Jede registrierte Szene
  läuft in jedem Frame, auch außerhalb des Bildes — also schreibt entweder nur die aktive Szene
  (`say()`), oder eine Funktion rechnet aus mehreren Eingängen (`applyField()`).
- Spaltenplatzierung steht in einer Klasse, nicht im `style`-Attribut: inline schlägt die Media
  Query und erzeugt auf einem Einspalten-Raster Spalten außerhalb des Viewports.

## Prüfen

```bash
python ../../skills/scrollcraft/scripts/scrollshot.py http://localhost:8000 --out .shots
```

Erwartet: keine Fehler, kein Overflow, nichts unsichtbar, Reload auf halber Höhe sauber,
Reduced-Motion vollständig aufgebaut — auf Desktop wie Telefon.

`scroll.js` ist eine wortgleiche Kopie von `skills/scrollcraft/assets/scaffold/scroll.js`, damit
die Seite eigenständig läuft. Wer die Engine ändert, prüft beides: Scaffold und diese Seite.
