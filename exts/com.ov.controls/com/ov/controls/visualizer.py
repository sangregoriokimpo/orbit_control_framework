from __future__ import annotations
import math
from typing import List, Dict

from pxr import UsdGeom, Gf, Vt
import omni.usd

from com.ov.core.orbit_math import TwoBodyRK4, Vec3

_body_colors: Dict[str, Gf.Vec3f] = {}

_PALETTE = [
    Gf.Vec3f(1.0,  0.35, 0.35),
    Gf.Vec3f(0.35, 0.75, 1.0),
    Gf.Vec3f(0.4,  1.0,  0.45),
    Gf.Vec3f(1.0,  0.8,  0.2),
    Gf.Vec3f(0.85, 0.4,  1.0),
    Gf.Vec3f(1.0,  0.55, 0.15),
    Gf.Vec3f(0.25, 1.0,  0.85),
    Gf.Vec3f(1.0,  0.4,  0.75),
]
_palette_index = 0


def _get_color(prim_path: str) -> Gf.Vec3f:
    global _palette_index
    if prim_path not in _body_colors:
        _body_colors[prim_path] = _PALETTE[_palette_index % len(_PALETTE)]
        _palette_index += 1
    return _body_colors[prim_path]


def _clear_color(prim_path: str):
    _body_colors.pop(prim_path, None)


def _apply_color(stage, curve_path: str, color: Gf.Vec3f):
    curves_prim = stage.GetPrimAtPath(curve_path)
    if not curves_prim or not curves_prim.IsValid():
        return
    curves = UsdGeom.Curves(curves_prim)
    color_attr = curves.GetDisplayColorAttr()
    if not color_attr:
        color_attr = curves.CreateDisplayColorAttr()
    color_attr.Set(Vt.Vec3fArray([color]))


def _simulate_orbit_points(mu: float, r0: Vec3, v0: Vec3, n_points: int = 256) -> List[Vec3]:
    rmag = math.sqrt(r0[0]**2 + r0[1]**2 + r0[2]**2)
    vmag = math.sqrt(v0[0]**2 + v0[1]**2 + v0[2]**2)
    a = 1.0 / (2.0 / rmag - vmag**2 / mu)
    if a <= 0:
        return []
    period = 2.0 * math.pi * math.sqrt(a**3 / mu)
    dt_step = period / n_points

    dyn = TwoBodyRK4(mu=mu, center=(0.0, 0.0, 0.0))
    r, v = r0, v0
    points = [r]
    for _ in range(n_points - 1):
        r, v = dyn.rk4_step(r, v, dt_step)
        points.append(r)
    return points


def _get_or_create_curves_prim(stage, path: str):
    prim = stage.GetPrimAtPath(path)
    if prim and prim.IsValid():
        return UsdGeom.BasisCurves(prim)
    return UsdGeom.BasisCurves.Define(stage, path)


def draw_orbit_path(prim_path: str, attractor_path: str, mu: float, r0: Vec3, v0: Vec3,
                    dt_sim: float, n_points: int = 256, curve_path: str = None):
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return None

    if curve_path is None:
        safe = prim_path.replace("/", "_").lstrip("_")
        curve_path = f"/OrbitViz/{safe}_path"

    aprim = stage.GetPrimAtPath(attractor_path)
    ax, ay, az = 0.0, 0.0, 0.0
    if aprim and aprim.IsValid():
        m = omni.usd.get_world_transform_matrix(aprim)
        p = m.ExtractTranslation()
        ax, ay, az = float(p[0]), float(p[1]), float(p[2])

    points = _simulate_orbit_points(mu, r0, v0, n_points)
    if not points:
        return None

    points.append(points[0])
    gf_points = Vt.Vec3fArray([Gf.Vec3f(ax + pt[0], ay + pt[1], az + pt[2]) for pt in points])

    curves = _get_or_create_curves_prim(stage, curve_path)
    curves.CreatePointsAttr(gf_points)
    curves.CreateCurveVertexCountsAttr(Vt.IntArray([len(gf_points)]))
    curves.CreateTypeAttr("linear")
    curves.CreateWrapAttr(UsdGeom.Tokens.periodic)

    _apply_color(stage, curve_path, _get_color(prim_path))

    return curve_path


def remove_orbit_path(curve_path: str, prim_path: str = None):
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return
    prim = stage.GetPrimAtPath(curve_path)
    if prim and prim.IsValid():
        stage.RemovePrim(curve_path)
    if prim_path:
        _clear_color(prim_path)


def remove_all_orbit_paths():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return
    prim = stage.GetPrimAtPath("/OrbitViz")
    if prim and prim.IsValid():
        stage.RemovePrim("/OrbitViz")
    _body_colors.clear()