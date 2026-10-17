# Mercedes 722.6 ATF-Service: Werkstatthilfen

Zwei parametrische Fusion-360-Modelle für den ATF-Service mit Spülung am
5-Gang-Automatikgetriebe 722.6, nach dem Ablauf im Video
[ATF-Service 722.6](https://youtu.be/jn3YhkkG6lE).

| Datei | Teil | Komponenten |
| --- | --- | --- |
| `flush_adapter.py` | Spüladapter für die Rücklaufleitung vom Ölkühler | Hohlschraube mit Schlauchtülle, Hutmutter, 2 Referenz-Alu-Dichtringe |
| `dipstick_lock.py` | Verriegelung für das Peilrohr | Stopfen mit Grifflasche, Verriegelungsstift mit Sollbruchstelle und Rastkegel |

## Ausführen

- **Über diesen MCP-Server:** den Dateiinhalt als `code` an `execute_code`
  senden. Das Skript baut in die aktive Konstruktion oder legt eine neue an.
- **Direkt in Fusion:** Utilities > Scripts and Add-Ins > `+` > Datei wählen.

Alle Maße stehen in mm im `PARAMS`-Dict am Dateianfang.

## Annahmen: vor der Fertigung messen

Die Maße stammen nicht vom Fahrzeug. Das Video zeigt keine Maße.

| Parameter | Annahme | Messen |
| --- | --- | --- |
| `thread` / `thread_d` | M14x1.5 | Gewinde der Hohlschraube an der Rücklaufleitung |
| `eye_width` | 12 mm | Breite des Leitungsauges |
| `seal_t`, `seal_od` | 1,5 mm, 20 mm (DIN 7603 A 14x20) | mitgelieferte Alu-Dichtringe |
| `barb_*` | Schlauch-ID 10 mm | eingesetzter Schlauch |
| `tube_od` | 13 mm | Außendurchmesser Peilrohr |
| `pin_from_top`, `pin_d` | 8 mm, 3 mm | Lage und Durchmesser der Stiftbohrung im Rohr |

## Fertigung

- **Spüladapter:** als Drehteil aus Aluminium oder Stahl, wie im Video
  („haben wir uns drehen lassen“). Mit `thread_modeled = False` ist das
  Gewinde kosmetisch und erscheint in der Zeichnung. Ein 3D-Druck ist für
  heißes ATF (ca. 80–100 °C) nicht zu empfehlen.
- **Verriegelung:** 3D-Druck in Rot, zum Beispiel PETG oder PA12. Der Stift
  bricht beim Öffnen an der Sollbruchstelle unter dem Kopf. Ist der Stift
  ab, war jemand am Getriebe.

Die Arbeitsanleitung (SOP) zum ATF-Service liegt als separates Dokument vor.
