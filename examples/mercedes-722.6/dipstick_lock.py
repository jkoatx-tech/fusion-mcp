"""Verriegelung fuer das ATF-Peilrohr (Mercedes 722.6): Stopfen + Stift.

Der Stopfen sitzt als Kappe auf dem Peilrohr, der Stift geht quer durch
Kappe und Rohr. Der Stift hat unter dem Kopf eine Sollbruchstelle und an
der Spitze einen geschlitzten Rastkegel: wer das Getriebe oeffnet, muss
ihn abbrechen. Rot drucken = "hier war schon jemand dran".

Alle Masse in mm stehen in PARAMS. Sie sind ANNAHMEN: Rohr-Aussen-
durchmesser und Bohrungslage am Fahrzeug messen.

Ausfuehren:
  - per MCP: Inhalt dieser Datei als `code` an `execute_code` senden
  - in Fusion: Utilities > Scripts and Add-Ins > Script aus dieser Datei
"""

import math

import adsk.core
import adsk.fusion

PARAMS = {
    # Peilrohr -- ANNAHMEN, am Fahrzeug messen
    "tube_od": 13.0,
    "fit_clearance": 0.3,  # radial, fuer 3D-Druck
    # Stopfen
    "cap_wall": 2.5,
    "cap_len": 25.0,
    "cap_top": 3.0,  # Deckenstaerke
    "pin_from_top": 8.0,  # Stiftachse unter der Oberkante
    "tab_w": 12.0,  # Grifflasche
    "tab_h": 10.0,
    "tab_t": 3.0,
    "tab_hole_d": 4.0,
    # Stift
    "pin_d": 3.0,
    "pin_hole_d": 3.3,
    "head_d": 7.0,
    "head_t": 1.5,
    "break_d": 2.0,  # Sollbruchstelle
    "barb_d": 3.9,
    "barb_tip_d": 2.4,
    "barb_len": 3.0,
    "slot_w": 0.8,
}


def _cm(mm):
    return mm / 10.0


def _new_component(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ.component


def _sketch_polyline(comp, plane, pts_xyz_mm):
    sk = comp.sketches.add(plane)
    pts = [
        sk.modelToSketchSpace(adsk.core.Point3D.create(_cm(x), _cm(y), _cm(z)))
        for x, y, z in pts_xyz_mm
    ]
    lines = sk.sketchCurves.sketchLines
    for a, b in zip(pts, pts[1:] + pts[:1]):
        lines.addByTwoPoints(a, b)
    return sk


def _revolve(comp, sketch, axis, operation, bodies=None):
    revs = comp.features.revolveFeatures
    inp = revs.createInput(sketch.profiles.item(0), axis, operation)
    inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
    if bodies:
        inp.participantBodies = bodies
    return revs.add(inp)


def _extrude_symmetric(comp, profile, total_mm, operation, bodies=None):
    # Symmetric, so the result does not depend on the plane's normal direction.
    exts = comp.features.extrudeFeatures
    inp = exts.createInput(profile, operation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(_cm(total_mm)), True)
    if bodies:
        inp.participantBodies = bodies
    return exts.add(inp)


def _circle_cut(comp, plane, center_xyz_mm, d_mm, length_mm, body):
    sk = comp.sketches.add(plane)
    x, y, z = center_xyz_mm
    center = sk.modelToSketchSpace(adsk.core.Point3D.create(_cm(x), _cm(y), _cm(z)))
    sk.sketchCurves.sketchCircles.addByCenterRadius(center, _cm(d_mm / 2))
    _extrude_symmetric(
        comp,
        sk.profiles.item(0),
        length_mm,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        [body],
    )


def build(design, p=PARAMS):
    root = design.rootComponent
    new_body = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation

    # Y = 0 is the pin axis; the cap opens downward over the tube.
    r_in = p["tube_od"] / 2 + p["fit_clearance"]
    r_out = r_in + p["cap_wall"]
    y_top = p["pin_from_top"]
    y_bot = y_top - p["cap_len"]

    cap = _new_component(root, "Peilrohr Stopfen")
    sk = _sketch_polyline(
        cap,
        cap.xYConstructionPlane,
        [
            (r_in, y_bot, 0),
            (r_out, y_bot, 0),
            (r_out, y_top, 0),
            (0, y_top, 0),
            (0, y_top - p["cap_top"], 0),
            (r_in, y_top - p["cap_top"], 0),
        ],
    )
    cap_body = _revolve(cap, sk, cap.yConstructionAxis, new_body).bodies.item(0)
    cap_body.name = "Stopfen"

    # Grip tab with a hole for a hook
    hw = p["tab_w"] / 2
    sk = _sketch_polyline(
        cap,
        cap.xYConstructionPlane,
        [
            (-hw, y_top - 1.0, 0),
            (hw, y_top - 1.0, 0),
            (hw, y_top + p["tab_h"], 0),
            (-hw, y_top + p["tab_h"], 0),
        ],
    )
    _extrude_symmetric(cap, sk.profiles.item(0), p["tab_t"], join, [cap_body])
    _circle_cut(
        cap,
        cap.xYConstructionPlane,
        (0, y_top + p["tab_h"] - p["tab_hole_d"] / 2 - 1.5, 0),
        p["tab_hole_d"],
        2 * p["tab_t"],
        cap_body,
    )
    # Cross hole for the pin, along X
    _circle_cut(
        cap,
        cap.yZConstructionPlane,
        (0, 0, 0),
        p["pin_hole_d"],
        2 * r_out + 2,
        cap_body,
    )

    # Pin along X: head on the -X side, barb beyond +X
    pin = _new_component(root, "Peilrohr Verriegelungsstift")
    x_head = -r_out - p["head_t"]
    x_barb = r_out + 0.5
    x_end = x_barb + p["barb_len"]
    rp, rb = p["pin_d"] / 2, p["break_d"] / 2
    sk = _sketch_polyline(
        pin,
        pin.xYConstructionPlane,
        [
            (x_head, 0, 0),
            (x_head, p["head_d"] / 2, 0),
            (-r_out, p["head_d"] / 2, 0),
            (-r_out, rp, 0),
            (-r_out + 0.5, rp, 0),
            (-r_out + 0.5, rb, 0),  # break-off groove
            (-r_out + 1.2, rb, 0),
            (-r_out + 1.2, rp, 0),
            (x_barb, rp, 0),
            (x_barb, p["barb_d"] / 2, 0),
            (x_end, p["barb_tip_d"] / 2, 0),
            (x_end, 0, 0),
        ],
    )
    pin_body = _revolve(pin, sk, pin.xConstructionAxis, new_body).bodies.item(0)
    pin_body.name = "Stift"

    # Slot through the barb so it can spring in
    hs = p["slot_w"] / 2
    sk = _sketch_polyline(
        pin,
        pin.xYConstructionPlane,
        [
            (r_out - 1.5, -hs, 0),
            (x_end + 1.0, -hs, 0),
            (x_end + 1.0, hs, 0),
            (r_out - 1.5, hs, 0),
        ],
    )
    _extrude_symmetric(pin, sk.profiles.item(0), p["barb_d"] + 2, cut, [pin_body])

    return (
        f"Verriegelung erzeugt: Stopfen ID {2 * r_in:.1f} / AD {2 * r_out:.1f} mm, "
        f"Stiftlaenge {x_end - x_head:.1f} mm"
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
