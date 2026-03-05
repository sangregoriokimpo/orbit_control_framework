import omni.ui as ui
import omni.usd

PLANES = ["xy", "xz", "yz"]


class ControlsUI:
    def __init__(self, ext, title="Orbit Controls"):
        self._ext = ext
        self._win = ui.Window(title, width=540, height=680)

        self._body_path      = ui.SimpleStringModel("/World/Cube")
        self._attractor_path = ui.SimpleStringModel("/World/Sphere")
        self._mu             = ui.SimpleFloatModel(980.665)
        self._dt             = ui.SimpleFloatModel(1.0 / 120.0)

        self._radius = ui.SimpleFloatModel(25.0)

        self._oe_a    = ui.SimpleFloatModel(25.0)
        self._oe_e    = ui.SimpleFloatModel(0.0)
        self._oe_inc  = ui.SimpleFloatModel(0.0)
        self._oe_raan = ui.SimpleFloatModel(0.0)
        self._oe_argp = ui.SimpleFloatModel(0.0)
        self._oe_nu   = ui.SimpleFloatModel(0.0)

        self._dvx = ui.SimpleFloatModel(0.0)
        self._dvy = ui.SimpleFloatModel(0.5)
        self._dvz = ui.SimpleFloatModel(0.0)

        self._target_x     = ui.SimpleFloatModel(0.0)
        self._target_y     = ui.SimpleFloatModel(0.0)
        self._target_z     = ui.SimpleFloatModel(1.0)
        self._kp           = ui.SimpleFloatModel(1.0)
        self._kd           = ui.SimpleFloatModel(2.0)
        self._amax         = ui.SimpleFloatModel(5.0)
        self._amax_enabled = ui.SimpleBoolModel(True)

        self._selected      = ui.SimpleStringModel("/World/Cube")
        self._status_model  = ui.SimpleStringModel("")

        self._build_ui()

    def _set_status(self, msg: str, ok: bool = True):
        self._status_model.set_value(("✓" if ok else "✗") + "  " + msg)

    def _pick_body(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if paths:
            self._body_path.set_value(paths[0])
            self._set_status(f"Body set to {paths[0]}")
        else:
            self._set_status("No prim selected in viewport", ok=False)

    def _pick_attractor(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if paths:
            self._attractor_path.set_value(paths[0])
            self._set_status(f"Attractor set to {paths[0]}")
        else:
            self._set_status("No prim selected in viewport", ok=False)

    def _pick_selected(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if paths:
            self._selected.set_value(paths[0])
            self._set_status(f"Controlling {paths[0]}")
        else:
            self._set_status("No prim selected in viewport", ok=False)

    def _refresh_state(self):
        p = self._selected.get_value_as_string()
        body = self._ext._svc.get_body(p)
        if not body:
            self._state_model.set_value(f"No body at {p}")
            return
        r, v = body.r, body.v
        self._state_model.set_value(
            f"mode: {body.control_mode}\n"
            f"r: ({r[0]:.2f}, {r[1]:.2f}, {r[2]:.2f})\n"
            f"v: ({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})"
        )

    def _build_ui(self):
        with self._win.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=6):

                    ui.Label("", height=4)
                    self._status_label = ui.Label("", style={"color": 0xFF88FF88}, height=22)
                    self._status_sub = self._status_model.subscribe_value_changed_fn(
                        lambda m: setattr(self._status_label, "text", m.get_value_as_string())
                    )

                    ui.Separator()

                    with ui.CollapsableFrame("Orbit Config", collapsed=False):
                        with ui.VStack(spacing=6):
                            with ui.HStack():
                                ui.Label("Body prim path", width=150)
                                ui.StringField(model=self._body_path)
                                ui.Button("◎", width=28, clicked_fn=self._pick_body,
                                          tooltip="Pick selected prim from viewport")
                            with ui.HStack():
                                ui.Label("Attractor prim path", width=150)
                                ui.StringField(model=self._attractor_path)
                                ui.Button("◎", width=28, clicked_fn=self._pick_attractor,
                                          tooltip="Pick selected prim from viewport")
                            with ui.HStack():
                                ui.Label("mu", width=150)
                                ui.FloatField(model=self._mu)
                            with ui.HStack():
                                ui.Label("dt_sim", width=150)
                                ui.FloatField(model=self._dt)

                    with ui.CollapsableFrame("Add Circular Orbit Body", collapsed=False):
                        with ui.VStack(spacing=6):
                            with ui.HStack():
                                ui.Label("radius", width=150)
                                ui.FloatField(model=self._radius)
                            with ui.HStack():
                                ui.Label("plane", width=150)
                                self._plane_combo = ui.ComboBox(0, "xy", "xz", "yz")
                                self._plane_idx = self._plane_combo.model.get_item_value_model()
                            ui.Button("Add / Replace Body (Circular)", clicked_fn=self._on_add_circular)

                    with ui.CollapsableFrame("Add Body via Orbital Elements", collapsed=True):
                        with ui.VStack(spacing=6):
                            for label, model in [
                                ("a  (semi-major axis)", self._oe_a),
                                ("e  (eccentricity)",    self._oe_e),
                                ("inc  (deg)",           self._oe_inc),
                                ("RAAN  (deg)",          self._oe_raan),
                                ("arg periapsis  (deg)", self._oe_argp),
                                ("true anomaly  (deg)",  self._oe_nu),
                            ]:
                                with ui.HStack():
                                    ui.Label(label, width=170)
                                    ui.FloatField(model=model)
                            ui.Button("Add / Replace Body (Elements)", clicked_fn=self._on_add_elements)

                    ui.Separator()

                    with ui.CollapsableFrame("Select & State", collapsed=False):
                        with ui.VStack(spacing=6):
                            with ui.HStack():
                                ui.Label("selected prim path", width=150)
                                ui.StringField(model=self._selected)
                                ui.Button("◎", width=28, clicked_fn=self._pick_selected,
                                          tooltip="Pick selected prim from viewport")
                            with ui.HStack():
                                ui.Button("Remove Body",   clicked_fn=self._on_remove)
                                ui.Button("Refresh State", clicked_fn=self._refresh_state)
                            with ui.HStack():
                                self._viz_model = ui.SimpleBoolModel(False)
                                ui.CheckBox(model=self._viz_model)
                                ui.Label("Show orbit paths", width=130)
                                ui.Button("Redraw All", clicked_fn=self._on_redraw_viz)
                            self._state_model = ui.SimpleStringModel("–")
                            ui.StringField(model=self._state_model, multiline=True,
                                           height=60, read_only=True)
                            self._viz_sub = self._viz_model.subscribe_value_changed_fn(
                                lambda m: self._ext.set_viz_enabled(m.get_value_as_bool())
                            )

                    ui.Separator()

                    with ui.CollapsableFrame("Impulse (Δv)", collapsed=False):
                        with ui.VStack(spacing=6):
                            with ui.HStack():
                                ui.Label("dv x", width=150)
                                ui.FloatField(model=self._dvx)
                            with ui.HStack():
                                ui.Label("dv y", width=150)
                                ui.FloatField(model=self._dvy)
                            with ui.HStack():
                                ui.Label("dv z", width=150)
                                ui.FloatField(model=self._dvz)
                            with ui.HStack():
                                ui.Button("Apply Δv",       clicked_fn=self._on_apply_dv)
                                ui.Button("+Prograde (+Y)", clicked_fn=self._on_prograde_pos)
                                ui.Button("-Prograde (-Y)", clicked_fn=self._on_prograde_neg)

                    ui.Separator()

                    with ui.CollapsableFrame("Dock / PD Hold", collapsed=False):
                        with ui.VStack(spacing=6):
                            ui.Label("Target offset (attractor-relative)")
                            with ui.HStack():
                                ui.Label("x", width=150)
                                ui.FloatField(model=self._target_x)
                            with ui.HStack():
                                ui.Label("y", width=150)
                                ui.FloatField(model=self._target_y)
                            with ui.HStack():
                                ui.Label("z", width=150)
                                ui.FloatField(model=self._target_z)
                            with ui.HStack():
                                ui.Button("Dock (snap)", clicked_fn=self._on_dock)
                                ui.Button("Undock",      clicked_fn=self._on_undock)
                            ui.Separator()
                            ui.Label("PD Hold")
                            with ui.HStack():
                                ui.Label("Kp", width=150)
                                ui.FloatField(model=self._kp)
                            with ui.HStack():
                                ui.Label("Kd", width=150)
                                ui.FloatField(model=self._kd)
                            with ui.HStack():
                                ui.Label("Limit acceleration", width=150)
                                ui.CheckBox(model=self._amax_enabled)
                            with ui.HStack():
                                ui.Label("a_max", width=150)
                                ui.FloatField(model=self._amax)
                            with ui.HStack():
                                ui.Button("Enable PD Hold", clicked_fn=self._on_pd_enable)
                                ui.Button("Disable PD",     clicked_fn=self._on_pd_disable)

                    ui.Separator()
                    ui.Button("List Bodies (prints)", clicked_fn=self._on_list)
                    ui.Spacer(height=12)

    def destroy(self):
        if self._win:
            self._win.visible = False
            self._win = None

    def _on_add_circular(self):
        body   = self._body_path.get_value_as_string()
        attr   = self._attractor_path.get_value_as_string()
        mu     = float(self._mu.get_value_as_float())
        dt     = float(self._dt.get_value_as_float())
        radius = float(self._radius.get_value_as_float())
        plane  = PLANES[int(self._plane_idx.get_value_as_int())] if 0 <= int(self._plane_idx.get_value_as_int()) < 3 else "xy"
        try:
            self._ext.add_body_circular(body, attr, mu, dt, radius, plane)
            self._selected.set_value(body)
            self._set_status(f"Added circular body {body}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_add_elements(self):
        body = self._body_path.get_value_as_string()
        attr = self._attractor_path.get_value_as_string()
        mu   = float(self._mu.get_value_as_float())
        dt   = float(self._dt.get_value_as_float())
        try:
            self._ext.add_body_elements(body, attr, mu, dt,
                float(self._oe_a.get_value_as_float()),
                float(self._oe_e.get_value_as_float()),
                float(self._oe_inc.get_value_as_float()),
                float(self._oe_raan.get_value_as_float()),
                float(self._oe_argp.get_value_as_float()),
                float(self._oe_nu.get_value_as_float()))
            self._selected.set_value(body)
            self._set_status(f"Added elements body {body}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_remove(self):
        p = self._selected.get_value_as_string()
        try:
            self._ext.remove_viz(p)
            self._ext._svc.remove_body(p)
            self._set_status(f"Removed {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_apply_dv(self):
        p  = self._selected.get_value_as_string()
        dv = (float(self._dvx.get_value_as_float()),
              float(self._dvy.get_value_as_float()),
              float(self._dvz.get_value_as_float()))
        try:
            self._ext.apply_impulse(p, dv)
            self._set_status(f"Δv applied to {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_prograde_pos(self):
        p  = self._selected.get_value_as_string()
        dv = float(self._dvy.get_value_as_float())
        self._ext.apply_impulse(p, (0.0, dv, 0.0))
        self._set_status(f"+Prograde {dv} applied to {p}")

    def _on_prograde_neg(self):
        p  = self._selected.get_value_as_string()
        dv = float(self._dvy.get_value_as_float())
        self._ext.apply_impulse(p, (0.0, -dv, 0.0))
        self._set_status(f"-Prograde {dv} applied to {p}")

    def _on_dock(self):
        p   = self._selected.get_value_as_string()
        off = (float(self._target_x.get_value_as_float()),
               float(self._target_y.get_value_as_float()),
               float(self._target_z.get_value_as_float()))
        try:
            self._ext.dock(p, off)
            self._set_status(f"Docked {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_undock(self):
        p = self._selected.get_value_as_string()
        try:
            self._ext.undock(p)
            self._set_status(f"Undocked {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_pd_enable(self):
        p    = self._selected.get_value_as_string()
        off  = (float(self._target_x.get_value_as_float()),
                float(self._target_y.get_value_as_float()),
                float(self._target_z.get_value_as_float()))
        kp   = float(self._kp.get_value_as_float())
        kd   = float(self._kd.get_value_as_float())
        amax = float(self._amax.get_value_as_float()) if self._amax_enabled.get_value_as_bool() else 0.0
        try:
            self._ext.enable_pd(p, off, kp, kd, amax)
            self._set_status(f"PD enabled on {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_pd_disable(self):
        p = self._selected.get_value_as_string()
        try:
            self._ext.disable_pd(p)
            self._set_status(f"PD disabled on {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_redraw_viz(self):
        try:
            self._ext.refresh_viz()
            self._set_status("Orbit paths redrawn")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_list(self):
        bodies = self._ext.print_bodies()
        if bodies:
            self._state_model.set_value("\n".join(bodies))
            self._set_status(f"{len(bodies)} body/bodies registered")
        else:
            self._state_model.set_value("No bodies registered")
            self._set_status("No bodies registered", ok=False)