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

        # self._selected      = ui.SimpleStringModel("/World/Cube")
        self._body_names: list[str] = []
        self._selected_combo = None  
        self._selector_frame: ui.Frame | None = None

        self._body_combo = None
        self._attractor_combo = None
        self._body_frame_circ: ui.Frame | None = None
        self._attractor_frame_circ: ui.Frame | None = None
        self._body_frame_elem: ui.Frame | None = None
        self._attractor_frame_elem: ui.Frame | None = None
        # self._body_frame: ui.Frame | None = None
        # self._attractor_frame: ui.Frame | None = None

        self._status_model  = ui.SimpleStringModel("")
        self._active_body_model = ui.SimpleStringModel("(none)")

        self._build_ui()

    def _set_status(self, msg: str, ok: bool = True):
        self._status_model.set_value(("✓" if ok else "✗") + "  " + msg)

    def _pick_body(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if paths:
            self._body_path.set_value(paths[0])
            # if self._body_frame:
            for f in [self._body_frame_circ, self._body_frame_elem]:
                if f:
                    f.rebuild()
            self._set_status(f"Body set to {paths[0]}")
        else:
            self._set_status("No prim selected in viewport", ok=False)

    def _pick_attractor(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if paths:
            self._attractor_path.set_value(paths[0])
            # if self._attractor_frame:
            for f in [self._attractor_frame_circ, self._attractor_frame_elem]:
                if f:
                    f.rebuild()
            self._set_status(f"Attractor set to {paths[0]}")
        else:
            self._set_status("No prim selected in viewport", ok=False)


    def _pick_selected(self):
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        if not paths:
            self._set_status("No prim selected in viewport", ok=False)
            return
        target = paths[0]
        self._refresh_selector()  
        if target in self._body_names:
            idx = self._body_names.index(target)
            self._selected_combo.model.get_item_value_model().set_value(idx)
            self._set_status(f"Controlling {target}")
        else:
            self._set_status(f"{target} is not a registered body", ok=False)

    def _get_stage_prims(self) -> list[str]:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return ["/World"]
        return [str(p.GetPath()) for p in stage.Traverse() 
                if p.IsValid() and not p.GetPath().IsRootPrimPath()]

    def _build_selector(self):
        bodies = self._ext._svc.list_bodies()
        self._body_names = bodies if bodies else []
        items = bodies if bodies else ["(no bodies)"]
        with ui.HStack():
            ui.Label("Selected body", width=150)
            self._selected_combo = ui.ComboBox(0, *items)
            self._selected_combo.model.get_item_value_model().add_value_changed_fn(
                lambda m: self._active_body_model.set_value(self._get_selected_path())
            )
            ui.Button("X", width=28, clicked_fn=self._pick_selected,
                    tooltip="Select body from viewport")
        self._active_body_model.set_value(self._get_selected_path())

    # def _pick_selected(self):
    #     paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
    #     if paths:
    #         self._selected.set_value(paths[0])
    #         self._set_status(f"Controlling {paths[0]}")
    #     else:
    #         self._set_status("No prim selected in viewport", ok=False)

    # def _build_selector(self):
    #     bodies = self._ext._svc.list_bodies()
    #     self._body_names = bodies if bodies else []
    #     items = bodies if bodies else ["(no bodies)"]
    #     with ui.HStack():
    #         ui.Label("Selected body", width=150)
    #         self._selected_combo = ui.ComboBox(0, *items)

    def _refresh_selector(self):
        if self._selector_frame is not None:
            self._selector_frame.rebuild()

    def _get_selected_path(self) -> str:
        if not self._body_names or self._selected_combo is None:
            return ""
        idx = self._selected_combo.model.get_item_value_model().get_value_as_int()
        idx = max(0, min(idx, len(self._body_names) - 1))
        return self._body_names[idx]

    def _refresh_state(self):
        p = self._get_selected_path()
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

    def _rebuild_body_list(self):
        bodies = self._ext._svc.list_bodies()
        self._body_names = bodies
        if self._selected_combo is not None:
            self._selected_combo.model.get_item_value_model().set_value(0)

    # def _build_body_picker(self):
    #     prims = self._get_stage_prims() or ["/World/Cube"]
    #     current = self._body_path.get_value_as_string()
    #     idx = prims.index(current) if current in prims else 0
    #     with ui.HStack():
    #         ui.Label("Body prim path", width=150)
    #         self._body_combo = ui.ComboBox(idx, *prims)
    #         self._body_combo.model.get_item_value_model().add_value_changed_fn(
    #             lambda m: self._body_path.set_value(
    #                 prims[max(0, min(m.get_value_as_int(), len(prims)-1))]
    #             )
    #         )
    #         ui.Button("X", width=28, clicked_fn=self._pick_body,
    #                 tooltip="Pick from viewport, then click Refresh")
    #         ui.Button("R", width=28, 
    #                 clicked_fn=lambda: self._body_frame.rebuild(),
    #                 tooltip="Refresh prim list from stage")

    # def _build_attractor_picker(self):
    #     prims = self._get_stage_prims() or ["/World/Sphere"]
    #     current = self._attractor_path.get_value_as_string()
    #     idx = prims.index(current) if current in prims else 0
    #     with ui.HStack():
    #         ui.Label("Attractor prim path", width=150)
    #         self._attractor_combo = ui.ComboBox(idx, *prims)
    #         self._attractor_combo.model.get_item_value_model().add_value_changed_fn(
    #             lambda m: self._attractor_path.set_value(
    #                 prims[max(0, min(m.get_value_as_int(), len(prims)-1))]
    #             )
    #         )
    #         ui.Button("X", width=28, clicked_fn=self._pick_attractor,
    #                 tooltip="Pick from viewport, then click Refresh")
    #         ui.Button("R", width=28,
    #                 clicked_fn=lambda: self._attractor_frame.rebuild(),
    #                 tooltip="Refresh prim list from stage")
            
    def _build_body_picker_circ(self):
        self._build_body_picker_into("_body_frame_circ")

    def _build_attractor_picker_circ(self):
        self._build_attractor_picker_into("_attractor_frame_circ")

    def _build_body_picker_elem(self):
        self._build_body_picker_into("_body_frame_elem")

    def _build_attractor_picker_elem(self):
        self._build_attractor_picker_into("_attractor_frame_elem")

    def _build_body_picker_into(self, frame_attr: str):
        prims = self._get_stage_prims() or ["/World/Cube"]
        current = self._body_path.get_value_as_string()
        if current not in prims:
            prims = [current] + prims
        idx = prims.index(current) if current in prims else 0
        with ui.HStack():
            ui.Label("Body prim path", width=150)
            combo = ui.ComboBox(idx, *prims)
            combo.model.get_item_value_model().add_value_changed_fn(
                lambda m, p=prims: self._body_path.set_value(
                    p[max(0, min(m.get_value_as_int(), len(p)-1))]
                )
            )
            ui.Button("X", width=28, clicked_fn=self._pick_body,
                    tooltip="Pick from viewport")
            ui.Button("R", width=28,
                    clicked_fn=lambda fa=frame_attr: getattr(self, fa).rebuild(),
                    tooltip="Refresh prim list from stage")

    def _build_attractor_picker_into(self, frame_attr: str):
        prims = self._get_stage_prims() or ["/World/Sphere"]
        current = self._attractor_path.get_value_as_string()
        if current not in prims:
            prims = [current] + prims
        idx = prims.index(current) if current in prims else 0
        with ui.HStack():
            ui.Label("Attractor prim path", width=150)
            combo = ui.ComboBox(idx, *prims)
            combo.model.get_item_value_model().add_value_changed_fn(
                lambda m, p=prims: self._attractor_path.set_value(
                    p[max(0, min(m.get_value_as_int(), len(p)-1))]
                )
            )
            ui.Button("X", width=28, clicked_fn=self._pick_attractor,
                    tooltip="Pick from viewport")
            ui.Button("R", width=28,
                    clicked_fn=lambda fa=frame_attr: getattr(self, fa).rebuild(),
                    tooltip="Refresh prim list from stage")

    def _build_ui(self):
        with self._win.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=6):

                    ui.Label("", height=4)
                    self._status_label = ui.Label("", style={"color": 0xFF88FF88}, height=22)
                    self._status_sub = self._status_model.subscribe_value_changed_fn(
                        lambda m: setattr(self._status_label, "text", m.get_value_as_string())
                    )

                    # ui.Separator()

                    # with ui.CollapsableFrame("Orbit Config", collapsed=False):
                    #     with ui.VStack(spacing=6):
                    #         with ui.HStack():
                    #             self._body_frame = ui.Frame()
                    #             self._body_frame.set_build_fn(self._build_body_picker)
                    #             self._attractor_frame = ui.Frame()
                    #             self._attractor_frame.set_build_fn(self._build_attractor_picker)
                    #             # ui.Label("Body prim path", width=150)
                    #             # ui.StringField(model=self._body_path)
                    #             # ui.Button("◎", width=28, clicked_fn=self._pick_body,
                    #             #           tooltip="Pick selected prim from viewport")
                    #         with ui.HStack():
                    #             ui.Label("Attractor prim path", width=150)
                    #             ui.StringField(model=self._attractor_path)
                    #             ui.Button("◎", width=28, clicked_fn=self._pick_attractor,
                    #                       tooltip="Pick selected prim from viewport")
                    #         with ui.HStack():
                    #             ui.Label("mu", width=150)
                    #             ui.FloatField(model=self._mu)
                    #         with ui.HStack():
                    #             ui.Label("dt_sim", width=150)
                    #             ui.FloatField(model=self._dt)

                    with ui.CollapsableFrame("Add Circular Orbit Body", collapsed=False):
                        with ui.VStack(spacing=6):
                            self._body_frame_circ = ui.Frame()
                            self._body_frame_circ.set_build_fn(self._build_body_picker_circ)
                            self._attractor_frame_circ = ui.Frame()
                            self._attractor_frame_circ.set_build_fn(self._build_attractor_picker_circ)
                                # ui.Label("Body prim path", width=150)
                                # ui.StringField(model=self._body_path)
                                # ui.Button("◎", width=28, clicked_fn=self._pick_body,
                                #         tooltip="Pick from viewport")
                            with ui.HStack():
                                ui.Label("mu", width=150)
                                ui.FloatField(model=self._mu)
                            with ui.HStack():
                                ui.Label("dt_sim", width=150)
                                ui.FloatField(model=self._dt)
                            ui.Separator()
                            with ui.HStack():
                                ui.Label("radius", width=150)
                                ui.FloatField(model=self._radius)
                            with ui.HStack():
                                ui.Label("plane", width=150)
                                self._plane_combo = ui.ComboBox(0, "xy", "xz", "yz")
                                self._plane_idx = self._plane_combo.model.get_item_value_model()
                            # with ui.HStack():
                            #     ui.Label("Attractor prim path", width=150)
                            #     ui.StringField(model=self._attractor_path)
                            #     ui.Button("X", width=28, clicked_fn=self._pick_attractor,
                            #             tooltip="Pick from viewport")
                            # with ui.HStack():
                            #     ui.Label("mu", width=150)
                            #     ui.FloatField(model=self._mu)
                            # with ui.HStack():
                            #     ui.Label("dt_sim", width=150)
                            #     ui.FloatField(model=self._dt)
                            # ui.Separator()
                            # with ui.HStack():
                            #     ui.Label("radius", width=150)
                            #     ui.FloatField(model=self._radius)
                            # with ui.HStack():
                            #     ui.Label("plane", width=150)
                            #     self._plane_combo = ui.ComboBox(0, "xy", "xz", "yz")
                            #     self._plane_idx = self._plane_combo.model.get_item_value_model()
                            # ui.Button("Add / Replace Body (Circular)", clicked_fn=self._on_add_circular)
                            # with ui.HStack():
                            #     ui.Label("radius", width=150)
                            #     ui.FloatField(model=self._radius)
                            # with ui.HStack():
                            #     ui.Label("plane", width=150)
                            #     self._plane_combo = ui.ComboBox(0, "xy", "xz", "yz")
                            #     self._plane_idx = self._plane_combo.model.get_item_value_model()
                            ui.Button("Add / Replace Body (Circular)", clicked_fn=self._on_add_circular)
                    ui.Separator()

                    with ui.CollapsableFrame("Add Body via Orbital Elements", collapsed=False):
                        with ui.VStack(spacing=6):
                            self._body_frame_elem = ui.Frame()
                            self._body_frame_elem.set_build_fn(self._build_body_picker_elem)
                            self._attractor_frame_elem = ui.Frame()
                            self._attractor_frame_elem.set_build_fn(self._build_attractor_picker_elem)                            
                            # with ui.HStack():
                            #     ui.Label("Body prim path", width=150)
                            #     ui.StringField(model=self._body_path)
                            #     ui.Button("X", width=28, clicked_fn=self._pick_body,
                            #             tooltip="Pick from viewport")
                            # with ui.HStack():
                            #     ui.Label("Attractor prim path", width=150)
                            #     ui.StringField(model=self._attractor_path)
                            #     ui.Button("X", width=28, clicked_fn=self._pick_attractor,
                            #             tooltip="Pick from viewport")
                            with ui.HStack():
                                ui.Label("mu", width=150)
                                ui.FloatField(model=self._mu)
                            with ui.HStack():
                                ui.Label("dt_sim", width=150)
                                ui.FloatField(model=self._dt)
                            ui.Separator()
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
                            # for label, model in [
                            #     ("a  (semi-major axis)", self._oe_a),
                            #     ("e  (eccentricity)",    self._oe_e),
                            #     ("inc  (deg)",           self._oe_inc),
                            #     ("RAAN  (deg)",          self._oe_raan),
                            #     ("arg periapsis  (deg)", self._oe_argp),
                            #     ("true anomaly  (deg)",  self._oe_nu),
                            # ]:
                            #     with ui.HStack():
                            #         ui.Label(label, width=170)
                            #         ui.FloatField(model=model)
                            # ui.Button("Add / Replace Body (Elements)", clicked_fn=self._on_add_elements)

                    ui.Separator()

                    with ui.CollapsableFrame("Select & State", collapsed=False):
                        with ui.VStack(spacing=6):
                            self._selector_frame = ui.Frame()
                            self._selector_frame.set_build_fn(self._build_selector)
                                # ui.Label("selected prim path", width=150)
                                # ui.StringField(model=self._selected)
                                # ui.Button("◎", width=28, clicked_fn=self._pick_selected,
                                #           tooltip="Pick selected prim from viewport")
                            with ui.HStack():
                                ui.Button("Remove Body",   clicked_fn=self._on_remove)
                                ui.Button("Refresh State", clicked_fn=self._refresh_state)
                            with ui.HStack():
                                self._viz_model = ui.SimpleBoolModel(False)
                                ui.CheckBox(model=self._viz_model)
                                ui.Label("Show orbit paths", width=130)
                                ui.Button("Redraw All", clicked_fn=self._on_redraw_viz)
                            with ui.HStack():
                                ui.Label("Viz update interval (frames)", width=150)
                                self._viz_interval = ui.SimpleIntModel(10)
                                ui.IntField(model=self._viz_interval)
                                ui.Button("Set", width=40, clicked_fn=self._on_set_viz_interval)
                            self._state_model = ui.SimpleStringModel("–")
                            ui.StringField(model=self._state_model, multiline=True,
                                           height=60, read_only=True)
                            self._viz_sub = self._viz_model.subscribe_value_changed_fn(
                                lambda m: self._ext.set_viz_enabled(m.get_value_as_bool())
                            )

                    ui.Separator()

                    with ui.CollapsableFrame("Impulse ( delta v)", collapsed=False):
                        with ui.VStack(spacing=6):
                            with ui.HStack():
                                ui.Label("Acting on:",width=80, style={"color":0xFF888888})
                                ui.StringField(model=self._active_body_model, read_only=True,style={"color": 0xFF88FF88})
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
                                ui.Button("Apply delta v",       clicked_fn=self._on_apply_dv)
                                ui.Button("+Prograde (+Y)", clicked_fn=self._on_prograde_pos)
                                ui.Button("-Prograde (-Y)", clicked_fn=self._on_prograde_neg)

                    ui.Separator()

                    with ui.CollapsableFrame("Dock / PD Hold", collapsed=False):
                        with ui.VStack(spacing=6):
                            ui.Label("Target offset (attractor-relative)")
                            with ui.HStack():
                                ui.Label("Acting on:", width=80, style={"color": 0xFF888888})
                                ui.StringField(model=self._active_body_model, read_only=True,style={"color": 0xFF88FF88})
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
            self._refresh_selector()
            if body in self._body_names:
                self._selected_combo.model.get_item_value_model().set_value(
                    self._body_names.index(body)
                )
            self._set_status(f"Added circular body {body}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)
        
        # try:
        #     self._ext.add_body_circular(body, attr, mu, dt, radius, plane)
        #     self._selected.set_value(body)
        #     self._set_status(f"Added circular body {body}")
        # except Exception as ex:
        #     self._set_status(str(ex), ok=False)

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
            # self._selected.set_value(body)
            self._refresh_selector()
            if body in self._body_names:
                self._selected_combo.model.get_item_value_model().set_value(
                    self._body_names.index(body)
                )
            self._set_status(f"Added elements body {body}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_remove(self):
        p = p = self._get_selected_path()
        try:
            self._ext.remove_viz(p)
            self._ext._svc.remove_body(p)
            self._refresh_selector()
            self._set_status(f"Removed {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_apply_dv(self):
        p  = p = self._get_selected_path()
        dv = (float(self._dvx.get_value_as_float()),
              float(self._dvy.get_value_as_float()),
              float(self._dvz.get_value_as_float()))
        try:
            self._ext.apply_impulse(p, dv)
            self._set_status(f"Δv applied to {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_prograde_pos(self):
        p  = p = self._get_selected_path()
        dv = float(self._dvy.get_value_as_float())
        self._ext.apply_impulse(p, (0.0, dv, 0.0))
        self._set_status(f"+Prograde {dv} applied to {p}")

    def _on_prograde_neg(self):
        p  = p = self._get_selected_path()
        dv = float(self._dvy.get_value_as_float())
        self._ext.apply_impulse(p, (0.0, -dv, 0.0))
        self._set_status(f"-Prograde {dv} applied to {p}")

    def _on_set_viz_interval(self):
        val = max(1, int(self._viz_interval.get_value_as_int()))
        self._viz_interval.set_value(val)
        self._ext._viz_update_interval = val
        self._set_status(f"Viz interval set to {val} frames")

    def _on_dock(self):
        p   = p = self._get_selected_path()
        off = (float(self._target_x.get_value_as_float()),
               float(self._target_y.get_value_as_float()),
               float(self._target_z.get_value_as_float()))
        try:
            self._ext.dock(p, off)
            self._set_status(f"Docked {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_undock(self):
        p = p = self._get_selected_path()
        try:
            self._ext.undock(p)
            self._set_status(f"Undocked {p}")
        except Exception as ex:
            self._set_status(str(ex), ok=False)

    def _on_pd_enable(self):
        p    = p = self._get_selected_path()
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
        p = p = self._get_selected_path()
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