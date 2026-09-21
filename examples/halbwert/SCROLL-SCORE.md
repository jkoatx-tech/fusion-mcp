# HALBWERT — Scroll-Score

Fiktives Studio, gebaut als Live-Test der Scrollcraft-Skill. Alle Zahlen, Namen und Termine sind
erfunden und auf der Seite als solche gekennzeichnet.

**Belief:** Dass ein zwanzig Jahre altes System abgeschaltet werden kann, ohne dass es jemand
merkt — und dass diese Leute wissen, wie.

**Register:** technisch-dokumentarisch. Messwerte statt Adjektive, Mono für alles Gemessene,
Grid und Linien sichtbar. Bewegung zeigt Mechanik.

**Signature Move:** Die Cutover-Nacht läuft unter der Hand des Lesers ab — Uhr, Verkehr,
Rollback-Fenster und Protokoll sind an die Scroll-Position gebunden und laufen rückwärts.

---

## Szene 00 — Hero
Claim:       Wir schalten Systeme ab, die niemand mehr abschalten will.
Mechanic:    Liste von Altsystemen erlischt nacheinander beim ersten Scrollen
Bound to:    track(), p 0→1 über die Hero-Höhe
Scroll cost: 90vh
Feel:        gespannt — eine Behauptung, ein Beweis, dass die Seite reagiert
Assets:      keine

## Szene 01 — Cutover  ◆ Signature
Claim:       23:47 bis 04:12. Ein System geht aus, eines geht an, niemand merkt es.
Mechanic:    pinned; Uhr, zwei Verkehrsbalken, Rollback-Fenster, Protokollzeilen
Bound to:    pin(), p 0→1; Uhr linear, Verkehr zwischen .25–.62, Rollback .35–.70
Scroll cost: 260vh
Feel:        intensiv — die ganze Seite hängt an dieser Szene
Assets:      CSS/SVG

## Szene 02 — Rückstand
Claim:       2,4 Mio. Zeilen entfernt. 318 Server aus. 1,9 Mio. € Betriebskosten weg.
Mechanic:    Feldwechsel nach dunkel am Übergang, danach drei gebundene Zähler
Bound to:    track() für das Feld, pin() für die Zähler; Zählung endet bei p .85
Scroll cost: 180vh
Feel:        intensiv — der Ertrag, direkt nach dem Aufwand
Assets:      keine

## Szene 03 — Methode
Claim:       Vier Schritte, jeder mit Dauer und Abbruchkriterium.
Mechanic:    Horizontal-Rail (Inventur, Schattenbetrieb, Cutover, Rückbau); mobil Swipe-Strip
Bound to:    pin() auf Desktop, track() auf Phone
Scroll cost: 320vh
Feel:        mittel — Achsenwechsel als Entlastung nach zwei intensiven Szenen
Assets:      keine

## Szene 04 — Grenzen
Claim:       Drei Dinge, die wir nicht tun.
Mechanic:    statisch, Marginalien im Raster, gestaffelte Reveals
Bound to:    reveal()
Scroll cost: 120vh
Feel:        ruhig — Glaubwürdigkeit kommt aus dem, was man ablehnt
Assets:      keine

## Szene 05 — Kontakt
Claim:       Erstgespräch, 45 Minuten, ohne Angebot am Ende.
Mechanic:    statisch
Scroll cost: 80vh
Feel:        ruhig
Assets:      keine

---

Budget gesamt ≈ 1050vh. Mechaniken: gebundener Zähler, Pinned Scene, Rail, Feldwechsel, Reveal —
fünf, keine zweimal hintereinander.
