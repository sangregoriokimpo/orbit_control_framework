from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

from .orbit_math import Vec3, TwoBodyRK4, FixedStepClock, circular_orbit_ic, coe_to_rv

@dataclass
class OrbitBody:
    prim_path: str
    attractor_path: str
    mu: float
    dt_sim: float

    # relative state (to attractor)
    r: Vec3
    v: Vec3

    # control modes: "free", "dock", "pd"
    control_mode: str = "free"

    # docking / target offset (in attractor-relative frame)
    target_offset: Vec3 = (0.0, 0.0, 0.0)

    # PD gains (for relative positioning)
    kp: float = 0.0
    kd: float = 0.0

    # RCS pulse limiting (optional). If a_max<=0 => unlimited (not recommended)
    a_max: float = 0.0

    enabled: bool = True

    # runtime (not user-set)
    _clock: FixedStepClock = field(default_factory=lambda: FixedStepClock(1/120))
    _dyn: TwoBodyRK4 = field(default_factory=lambda: TwoBodyRK4(1.0))


class OrbitService:
    """
    Core API used by other extensions (UI/controls).
    """
    def __init__(self):
        self._bodies: Dict[str, OrbitBody] = {}

    # ---------- creation ----------
    def add_body_circular(self, prim_path: str, attractor_path: str, mu: float, dt_sim: float, radius: float, plane: str = "xy"):
        r0, v0 = circular_orbit_ic(mu, radius, plane=plane)
        body = OrbitBody(
            prim_path=prim_path,
            attractor_path=attractor_path,
            mu=float(mu),
            dt_sim=float(dt_sim),
            r=r0,
            v=v0,
        )
        body._clock = FixedStepClock(dt_sim=float(dt_sim))
        body._dyn = TwoBodyRK4(mu=float(mu), center=(0.0, 0.0, 0.0))
        self._bodies[prim_path] = body
        return body

    def add_body_elements(self, prim_path: str, attractor_path: str, mu: float, dt_sim: float,
                          a: float, e: float, inc_deg: float, raan_deg: float, argp_deg: float, nu_deg: float):
        import math
        inc = math.radians(float(inc_deg))
        raan = math.radians(float(raan_deg))
        argp = math.radians(float(argp_deg))
        nu = math.radians(float(nu_deg))
        r0, v0 = coe_to_rv(float(mu), float(a), float(e), inc, raan, argp, nu)

        body = OrbitBody(
            prim_path=prim_path,
            attractor_path=attractor_path,
            mu=float(mu),
            dt_sim=float(dt_sim),
            r=r0,
            v=v0,
        )
        body._clock = FixedStepClock(dt_sim=float(dt_sim))
        body._dyn = TwoBodyRK4(mu=float(mu), center=(0.0, 0.0, 0.0))
        self._bodies[prim_path] = body
        return body

    def remove_body(self, prim_path: str):
        self._bodies.pop(prim_path, None)

    def list_bodies(self) -> List[str]:
        return list(self._bodies.keys())

    def get_body(self, prim_path: str) -> Optional[OrbitBody]:
        return self._bodies.get(prim_path)

    # ---------- control primitives ----------
    def apply_impulse(self, prim_path: str, dv: Vec3):
        b = self._bodies.get(prim_path)
        if not b:
            return
        b.v = (b.v[0] + dv[0], b.v[1] + dv[1], b.v[2] + dv[2])

    def set_dock(self, prim_path: str, offset: Vec3):
        b = self._bodies.get(prim_path)
        if not b:
            return
        b.control_mode = "dock"
        b.target_offset = offset

    def clear_dock(self, prim_path: str):
        b = self._bodies.get(prim_path)
        if not b:
            return
        if b.control_mode == "dock":
            b.control_mode = "free"

    def set_pd_hold(self, prim_path: str, target_offset: Vec3, kp: float, kd: float, a_max: float = 0.0):
        b = self._bodies.get(prim_path)
        if not b:
            return
        b.control_mode = "pd"
        b.target_offset = target_offset
        b.kp = float(kp)
        b.kd = float(kd)
        b.a_max = float(a_max)

    def clear_pd(self, prim_path: str):
        b = self._bodies.get(prim_path)
        if not b:
            return
        if b.control_mode == "pd":
            b.control_mode = "free"

    # ---------- simulation step ----------
    def step_body(self, prim_path: str, dt_frame: float):
        b = self._bodies.get(prim_path)
        if not b or not b.enabled:
            return

        n = b._clock.steps(dt_frame)
        if n <= 0:
            return

        for _ in range(n):
            # control accel in attractor-relative frame
            a_cmd = (0.0, 0.0, 0.0)

            if b.control_mode == "dock":
                # Hard constraint: force r to target offset, zero velocity
                b.r = b.target_offset
                b.v = (0.0, 0.0, 0.0)
                continue

            if b.control_mode == "pd":
                # PD on relative position error
                ex = b.target_offset[0] - b.r[0]
                ey = b.target_offset[1] - b.r[1]
                ez = b.target_offset[2] - b.r[2]
                evx = 0.0 - b.v[0]
                evy = 0.0 - b.v[1]
                evz = 0.0 - b.v[2]

                ax = b.kp * ex + b.kd * evx
                ay = b.kp * ey + b.kd * evy
                az = b.kp * ez + b.kd * evz

                if b.a_max and b.a_max > 0.0:
                    # clamp magnitude
                    import math
                    amag = math.sqrt(ax*ax + ay*ay + az*az)
                    if amag > b.a_max:
                        s = b.a_max / amag
                        ax, ay, az = ax*s, ay*s, az*s

                a_cmd = (ax, ay, az)

            # Integrate (gravity + a_cmd)
            b.r, b.v = b._dyn.rk4_step(b.r, b.v, b.dt_sim, a_cmd=a_cmd)


# Singleton getter (used by controls extension)
_SERVICE: Optional[OrbitService] = None

def get_orbit_service() -> OrbitService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = OrbitService()
    return _SERVICE