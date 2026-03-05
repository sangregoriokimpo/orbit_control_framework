import omni.ext
import omni.kit.context_menu
import omni.kit.app
from com.ov.core.service import get_orbit_service

from .ui import ControlsUI
from .visualizer import draw_orbit_path, remove_orbit_path, remove_all_orbit_paths


class OrbitControlsExtension(omni.ext.IExt):

    def on_startup(self, ext_id: str):
        self._svc = get_orbit_service()
        self._ui = ControlsUI(self)
        self._viz_enabled = False
        self._viz_paths: dict = {}
        self._menu_handles = []
        self._frame_count = 0
        self._viz_update_interval = 1  # redraw every N frames

        # subscribe to app update loop
        self._app = omni.kit.app.get_app()
        self._update_sub = self._app.get_update_event_stream().create_subscription_to_pop(
            self._on_update
        )

        self._register_context_menu()
        print("[OrbitControls] started")

    def on_shutdown(self):
        if self._update_sub:
            self._update_sub.unsubscribe()
            self._update_sub = None
        self._unregister_context_menu()
        remove_all_orbit_paths()
        if self._ui:
            self._ui.destroy()
            self._ui = None
        print("[OrbitControls] shutdown")

    def _on_update(self, e):
        if not self._viz_enabled:
            return
        self._frame_count += 1
        if self._frame_count % self._viz_update_interval == 0:
            self.refresh_viz()

    # def on_startup(self, ext_id: str):
    #     self._svc = get_orbit_service()
    #     self._ui = ControlsUI(self)
    #     self._viz_enabled = False
    #     self._viz_paths: dict = {}
    #     self._menu_handles = []
    #     self._register_context_menu()
    #     print("[OrbitControls] started")

    # def on_shutdown(self):
    #     self._unregister_context_menu()
    #     remove_all_orbit_paths()
    #     if self._ui:
    #         self._ui.destroy()
    #         self._ui = None
    #     print("[OrbitControls] shutdown")

    def set_viz_enabled(self, enabled: bool):
        self._viz_enabled = enabled
        if not enabled:
            remove_all_orbit_paths()
            self._viz_paths.clear()

    def refresh_viz(self, prim_path: str = None):
        if not self._viz_enabled:
            return
        targets = [prim_path] if prim_path else list(self._svc.list_bodies())
        for p in targets:
            body = self._svc.get_body(p)
            if not body:
                continue
            safe = p.replace("/", "_").lstrip("_")
            curve_path = f"/OrbitViz/{safe}_path"
            drawn = draw_orbit_path(
                prim_path=p,
                attractor_path=body.attractor_path,
                mu=body.mu,
                r0=body.r,
                v0=body.v,
                dt_sim=body.dt_sim,
                curve_path=curve_path,
            )
            if drawn:
                self._viz_paths[p] = drawn

    def remove_viz(self, prim_path: str):
        curve_path = self._viz_paths.pop(prim_path, None)
        if curve_path:
            remove_orbit_path(curve_path, prim_path=prim_path)

    def _register_context_menu(self):
        ctx = omni.kit.context_menu.get_instance()

        def _is_prim_selected(objects):
            return bool(objects.get("prim_list"))

        def _set_as_attractor(objects):
            prims = objects.get("prim_list", [])
            if prims:
                path = str(prims[0].GetPath())
                self._svc.last_selected_attractor = path
                print(f"[OrbitControls] Set attractor: {path}")

        def _add_circular_body(objects):
            prims = objects.get("prim_list", [])
            if not prims:
                return
            path = str(prims[0].GetPath())
            attractor = getattr(self._svc, "last_selected_attractor", "/World/Sphere")
            self._svc.add_body_circular(path, attractor, mu=980.665, dt_sim=1/120, radius=25.0, plane="xy")
            self.refresh_viz(path)
            print(f"[OrbitControls] Quick-added circular body: {path}")

        try:
            handle = ctx.add_menu([
                {
                    "name": "Orbit",
                    "show_fn": _is_prim_selected,
                    "items": [
                        {"name": "Set as Attractor",   "onclick_fn": _set_as_attractor, "show_fn": _is_prim_selected},
                        {"name": "Add Circular Orbit", "onclick_fn": _add_circular_body, "show_fn": _is_prim_selected},
                    ],
                }
            ], "MENU")
            if handle:
                self._menu_handles.append(handle)
        except Exception as e:
            print(f"[OrbitControls] Context menu registration failed: {e}")

    def _unregister_context_menu(self):
        try:
            ctx = omni.kit.context_menu.get_instance()
            for h in self._menu_handles:
                ctx.remove_menu(h)
        except Exception as e:
            print(f"[OrbitControls] Context menu unregister failed: {e}")
        self._menu_handles = []

    def add_body_circular(self, prim_path, attractor_path, mu, dt_sim, radius, plane):
        self._svc.add_body_circular(prim_path, attractor_path, mu, dt_sim, radius, plane)
        self.refresh_viz(prim_path)
        print("[OrbitControls] add circular:", prim_path, "around", attractor_path)

    def add_body_elements(self, prim_path, attractor_path, mu, dt_sim, a, e, inc, raan, argp, nu):
        self._svc.add_body_elements(prim_path, attractor_path, mu, dt_sim, a, e, inc, raan, argp, nu)
        self.refresh_viz(prim_path)
        print("[OrbitControls] add elements:", prim_path, "around", attractor_path)

    def apply_impulse(self, prim_path, dv):
        self._svc.apply_impulse(prim_path, dv)
        self.refresh_viz(prim_path)
        print("[OrbitControls] dv:", prim_path, dv)

    def dock(self, prim_path, offset):
        self._svc.set_dock(prim_path, offset)
        print("[OrbitControls] dock:", prim_path, offset)

    def undock(self, prim_path):
        self._svc.clear_dock(prim_path)
        self.refresh_viz(prim_path)
        print("[OrbitControls] undock:", prim_path)

    def enable_pd(self, prim_path, target_offset, kp, kd, a_max):
        self._svc.set_pd_hold(prim_path, target_offset, kp, kd, a_max=a_max)
        print("[OrbitControls] pd:", prim_path, target_offset, kp, kd, a_max)

    def disable_pd(self, prim_path):
        self._svc.clear_pd(prim_path)
        self.refresh_viz(prim_path)
        print("[OrbitControls] pd off:", prim_path)

    def print_bodies(self):
        bodies = self._svc.list_bodies()
        print("[OrbitControls] bodies:", bodies)
        return bodies