"""Spueladapter fuer die ATF-Ruecklaufleitung (Mercedes 722.6).

Hohlschraube mit Schlauchtuelle statt Kopf: sie geht durch das Auge der
Ruecklaufleitung (Alu-Dichtring beidseitig) und wird mit einer Hutmutter
geklemmt. Das ATF vom Oelkuehler laeuft ueber die Querbohrungen in die
Axialbohrung und durch die Tuelle in den Schlauch zum Kanister.

Alle Masse in mm stehen in PARAMS. Die Gewinde- und Augenmasse sind
Annahmen: am Fahrzeug messen, bevor das Teil gedreht wird.

Ausfuehren:
  - per MCP: Inhalt dieser Datei als `code` an `execute_code` senden
  - in Fusion: Utilities > Scripts and Add-Ins > Script aus dieser Datei
"""

import math

import adsk.core
import adsk.fusion

PARAMS = {
    # Hohlschraube -- ANNAHMEN, am Fahrzeug pruefen
    "thread": "M14x1.5",
    "thread_d": 14.0,
    "eye_width": 12.0,  # Breite des Leitungsauges
    "seal_t": 1.5,  # Alu-Dichtring DIN 7603 A 14x20
    "seal_od": 20.0,
    # Schraube
    "collar_d": 21.0,  # Dichtbund unter dem Sechskant
    "collar_h": 3.0,
    "hex_af": 17.0,
    "hex_h": 8.0,
    "bore_d": 6.0,  # Axialbohrung
    "cross_d": 4.0,  # 2 Querbohrungen, 90 Grad versetzt
    # Schlauchtuelle fuer Schlauch-ID 10
    "barb_base_d": 9.5,
    "barb_max_d": 11.5,
    "barb_len": 6.0,
    "barb_count": 3,
    "neck_len": 3.0,
    # Hutmutter
    "nut_af": 22.0,
    "nut_thread_depth": 11.0,
    "nut_wall": 4.0,
    "tap_d": 12.5,  # Kernloch M14x1.5
    # True = modelliertes Gewinde (3D-Druck), False = kosmetisch (Drehteil)
    "thread_modeled": False,
}


def _cm(mm):
    return mm / 10.0


def _new_component(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ.component


def _revolve(comp, pts_mm, operation, bodies=None):
    """Revolve a closed (r, y) polyline in mm about the Y axis."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    pts = [
        sk.modelToSketchSpace(adsk.core.Point3D.create(_cm(r), _cm(y), 0))
        for r, y in pts_mm
    ]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        lines.addByTwoPoints(a, b)
    revs = comp.features.revolveFeatures
    inp = revs.createInput(sk.profiles.item(0), comp.yConstructionAxis, operation)
    inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
    if bodies:
        inp.participantBodies = bodies
    return revs.add(inp)


def _hex_prism(comp, af_mm, y0_mm, h_mm, operation, bodies=None):
    """Hexagon prism along Y from y0 to y0 + h, centered on the Y axis."""
    planes = comp.constructionPlanes
    pin = planes.createInput()
    # The offset runs along the XZ plane's normal; divide by its Y sign.
    normal_y = comp.xZConstructionPlane.geometry.normal.y
    pin.setByOffset(
        comp.xZConstructionPlane,
        adsk.core.ValueInput.createByReal(_cm(y0_mm + h_mm / 2) / normal_y),
    )
    sk = comp.sketches.add(planes.add(pin))
    r = af_mm / math.sqrt(3)  # circumradius
    y_mid = y0_mm + h_mm / 2
    pts = [
        sk.modelToSketchSpace(
            adsk.core.Point3D.create(
                _cm(r * math.cos(math.radians(60 * i))),
                _cm(y_mid),
                _cm(r * math.sin(math.radians(60 * i))),
            )
        )
        for i in range(6)
    ]
    lines = sk.sketchCurves.sketchLines
    for a, b in zip(pts, pts[1:] + pts[:1]):
        lines.addByTwoPoints(a, b)
    return _extrude_symmetric(comp, sk.profiles.item(0), h_mm, operation, bodies)


def _extrude_symmetric(comp, profile, total_mm, operation, bodies=None):
    # Symmetric, so the result does not depend on the plane's normal direction.
    exts = comp.features.extrudeFeatures
    inp = exts.createInput(profile, operation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(_cm(total_mm)), True)
    if bodies:
        inp.participantBodies = bodies
    return exts.add(inp)


def _cross_hole(comp, plane, y_mm, d_mm, length_mm, body):
    sk = comp.sketches.add(plane)
    center = sk.modelToSketchSpace(adsk.core.Point3D.create(0, _cm(y_mm), 0))
    sk.sketchCurves.sketchCircles.addByCenterRadius(center, _cm(d_mm / 2))
    _extrude_symmetric(
        comp,
        sk.profiles.item(0),
        length_mm,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        [body],
    )


def _add_thread(comp, body, radius_mm, internal, p):
    """Thread the lowest cylindrical face of the given radius."""
    faces = [
        f
        for f in body.faces
        if f.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType
        and abs(adsk.core.Cylinder.cast(f.geometry).radius - _cm(radius_mm)) < 1e-4
    ]
    if not faces:
        return "kein Gewindezylinder gefunden"
    face = min(faces, key=lambda f: f.boundingBox.minPoint.y)
    tf = comp.features.threadFeatures
    info = tf.createThreadInfo(
        internal, "ISO Metric profile", p["thread"], "6H" if internal else "6g"
    )
    inp = tf.createInput(face, info)
    inp.isFullLength = True
    inp.isModeled = p["thread_modeled"]
    try:
        tf.add(inp)
        return "ok"
    except Exception as exc:  # thread table differs between Fusion versions
        return f"Gewinde nicht erzeugt: {exc}"


def build(design, p=PARAMS):
    root = design.rootComponent
    new_body = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation

    # Y = 0 is the sealing face under the collar; the stack goes down:
    # seal ring, line eye, seal ring, cap nut.
    s, e = p["seal_t"], p["eye_width"]
    y_nut = -(2 * s + e)
    y_cross = -(s + e / 2)
    y_end = y_nut - (p["nut_thread_depth"] - 1.0)
    r_t = p["thread_d"] / 2
    r_groove = p["tap_d"] / 2 - 0.1
    r_core = p["hex_af"] / 2 - 0.5
    r_base, r_max = p["barb_base_d"] / 2, p["barb_max_d"] / 2
    y_hex = p["collar_h"]
    y_barb = y_hex + p["hex_h"] + p["neck_len"]
    y_top = y_barb + p["barb_count"] * p["barb_len"]
    y_bore = y_cross - p["cross_d"]

    # Banjo bolt with hose barb
    bolt = _new_component(root, "Spueladapter Hohlschraube")
    profile = [
        (0, y_end),
        (r_t - 1.0, y_end),
        (r_t, y_end + 1.0),
        (r_t, y_nut + 0.5),
        (r_groove, y_nut + 0.5),  # thread undercut
        (r_groove, y_nut + 2.0),
        (r_t, y_nut + 2.0),
        (r_t, 0),
        (p["collar_d"] / 2, 0),
        (p["collar_d"] / 2, y_hex),
        (r_core, y_hex),
        (r_core, y_hex + p["hex_h"]),
        (r_base, y_hex + p["hex_h"]),
    ]
    profile.append((r_base, y_barb))
    for i in range(p["barb_count"]):
        y0 = y_barb + i * p["barb_len"]
        profile += [(r_max, y0), (r_base, y0 + p["barb_len"])]
    profile += [
        (p["bore_d"] / 2, y_top),
        (p["bore_d"] / 2, y_bore),
        (0, y_bore),
    ]
    body = _revolve(bolt, profile, new_body).bodies.item(0)
    body.name = "Hohlschraube"
    _hex_prism(bolt, p["hex_af"], y_hex, p["hex_h"], join, [body])
    _cross_hole(bolt, bolt.xYConstructionPlane, y_cross, p["cross_d"], 3 * r_t, body)
    _cross_hole(bolt, bolt.yZConstructionPlane, y_cross, p["cross_d"], 3 * r_t, body)
    bolt_thread = _add_thread(bolt, body, r_t, False, p)

    # Cap nut
    nut = _new_component(root, "Spueladapter Hutmutter")
    nut_h = p["nut_thread_depth"] + p["nut_wall"]
    nut_body = _hex_prism(nut, p["nut_af"], y_nut - nut_h, nut_h, new_body).bodies.item(
        0
    )
    nut_body.name = "Hutmutter"
    _revolve(
        nut,
        [
            (0, y_nut + 1.0),
            (p["tap_d"] / 2, y_nut + 1.0),
            (p["tap_d"] / 2, y_nut - p["nut_thread_depth"]),
            (0, y_nut - p["nut_thread_depth"]),
        ],
        cut,
        [nut_body],
    )
    nut_thread = _add_thread(nut, nut_body, p["tap_d"] / 2, True, p)

    # Reference seal rings (not manufactured)
    seals = _new_component(root, "Referenz Alu-Dichtringe")
    r_in = r_t + 0.1
    for y0 in (-s, y_nut):
        _revolve(
            seals,
            [
                (r_in, y0),
                (p["seal_od"] / 2, y0),
                (p["seal_od"] / 2, y0 + s),
                (r_in, y0 + s),
            ],
            new_body,
        )

    return (
        f"Spueladapter erzeugt: Laenge {y_top - y_end:.1f} mm, "
        f"Gewinde Schraube: {bolt_thread}, Gewinde Mutter: {nut_thread}"
    )


def _active_design(app):
    design = adsk.fusion.Design.cast(app.activeProduct) if app.activeProduct else None
    if design is None:
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
    return design


def run(context):
    app = adsk.core.Application.get()
    try:
        app.userInterface.messageBox(build(_active_design(app)))
    except Exception as exc:
        app.userInterface.messageBox(f"Fehler: {exc}")


# execute_code injects `app` and `ui`; a Fusion script defines neither.
if "app" in globals() and "ui" in globals():
    print(build(_active_design(globals()["app"])))
