# =============================
# app.py
# =============================

from datetime import datetime
from kivy.clock import Clock

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, DictProperty, ListProperty, NumericProperty, BooleanProperty
from kivymd.app import MDApp

from screens.notes_screen import NotesController

from math import atan2, degrees
from kivy.uix.widget import Widget


# Dev window size
Window.size = (320, 600)
Window.minimum_width = 320
Window.minimum_height = 600


class MetronomeDial(Widget):
    """Rotatable dial: 1 BPM per 22.5 degrees (1/16 of a full turn)."""
    # current visual angle (0..360) — used by KV canvas to rotate the hand
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dragging = False
        self._start_bpm = 0
        self._last_ang = 0.0
        self._accum_deg = 0.0

    def _angle_from_touch(self, touch):
        cx, cy = self.center
        dx, dy = touch.x - cx, touch.y - cy
        ang = degrees(atan2(dy, dx))  # -180..180
        if ang < 0:
            ang += 360
        return ang  # 0..360

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        self._dragging = True
        self._last_ang = self._angle_from_touch(touch)
        self._accum_deg = 0.0
        app = MDApp.get_running_app()
        self._start_bpm = app.bpm
        return True

    def on_touch_move(self, touch):
        if not self._dragging:
            return super().on_touch_move(touch)

        ang = self._angle_from_touch(touch)

        # incremental delta since last event, normalized to (-180, 180]
        d = ang - self._last_ang
        if d > 180:
            d -= 360
        elif d <= -180:
            d += 360

        self._accum_deg -= d
        self._last_ang = ang

        step_deg = 22.5  # 1/16 turn per BPM
        bpm_delta = int(round(self._accum_deg / step_deg))

        app = MDApp.get_running_app()
        new_bpm = max(30, min(300, self._start_bpm + bpm_delta))
        if new_bpm != app.bpm:
            app.bpm = new_bpm

        # keep visual angle growing; no modulo so it won't snap
        self.angle = app.bpm * step_deg
        return True

    def on_touch_up(self, touch):
        if self._dragging:
            self._dragging = False
            return True
        return super().on_touch_up(touch)


class RCApp(MDApp):
    # FS / notes
    fs = DictProperty({})
    current_path = ListProperty([])
    sort_mode = StringProperty("date")
    sort_label = StringProperty("Date")
    current_folder_name = StringProperty("")
    open_note_id = StringProperty("")
    open_note_title = StringProperty("")
    open_note_body = StringProperty("")

    # Timer sub-mode state
    timer_mode = StringProperty("metronome")
    # Metronome state
    bpm = NumericProperty(60)
    is_metronome_running = BooleanProperty(False)

    def build(self):
        self.title = "RealCalisthenics (Prototype)"
        self.theme_cls.theme_style = "Dark"
        root = Builder.load_file("kv/base.kv")
        self.notes = NotesController(self)
        return root

    def on_start(self):
        now = datetime.now().isoformat()
        self.fs = {
            "root": {
                "id": "root",
                "name": "",
                "type": "folder",
                "created": now,
                "children": [
                    {
                        "id": "f1",
                        "name": "Calisthenics",
                        "type": "folder",
                        "created": now,
                        "children": [
                            {"id": "n1", "name": "Planche ideas",
                                "type": "note", "created": now, "content": ""},
                            {"id": "n2", "name": "Front lever drills",
                                "type": "note", "created": now, "content": ""},
                        ],
                    },
                    {"id": "f2", "name": "Work", "type": "folder",
                        "created": now, "children": []},
                    {"id": "n3", "name": "Shopping list",
                        "type": "note", "created": now, "content": ""},
                ],
            }
        }
        self._set_active_icon("notes")
        self.notes.render_browser()

        # Initialize timer sub-mode after widgets are built
        Clock.schedule_once(lambda dt: self.switch_timer_mode("metronome"), 0)

    # -------- Bottom bar (Notes / Timer) --------

    def switch_tab(self, name: str):
        sm = self.root.ids.sm
        order = ["notes", "note_view", "timer"]
        current = sm.current
        if name not in order or current not in order:
            sm.current = name
        else:
            if order.index(name) > order.index(current):
                sm.transition.direction = "left"
            elif order.index(name) < order.index(current):
                sm.transition.direction = "right"
            sm.current = name

        active = "notes" if name in ("notes", "note_view") else "timer"
        self._set_active_icon(active)

        if name == "timer":
            Clock.schedule_once(lambda dt: self._highlight_timer_icons(), 0)

     # -------- Metronome actions --------

    def toggle_metronome(self):
        if self.is_metronome_running:
            self.stop_metronome()
        else:
            self.start_metronome()

    def start_metronome(self):
        self.is_metronome_running = True
        # (tick scheduling & sound will be added later)

    def stop_metronome(self):
        self.is_metronome_running = False
        # (cancel tick scheduling later)

    def _set_active_icon(self, name: str):
        notes_icon = self.root.ids.tab_notes
        timer_icon = self.root.ids.tab_timer
        if name == "notes":
            notes_icon.text_color = self.theme_cls.primary_color
            timer_icon.text_color = self.theme_cls.text_color
        else:
            timer_icon.text_color = self.theme_cls.primary_color
            notes_icon.text_color = self.theme_cls.text_color

    # -------- Timer sub-mode (Metronome / Timer / Stopwatch) --------
    def switch_timer_mode(self, mode: str):
        """Switch the content inside the Timer screen and highlight the active icon."""
        order = ["metronome", "timer", "stopwatch"]
        if mode not in order:
            raise ValueError(f"Unknown timer mode: {mode}")

        modes = self.root.ids.get("timer_modes")
        if modes is None:
            # Tree not ready yet; try again next frame
            Clock.schedule_once(lambda dt: self.switch_timer_mode(mode), 0)
            return

        current = self.timer_mode if self.timer_mode in order else "metronome"

        # Slide direction + duration (page transitions ON)
        if order.index(mode) > order.index(current):
            modes.transition.direction = "left"
        elif order.index(mode) < order.index(current):
            modes.transition.direction = "right"
        modes.transition.duration = 0.20

        modes.current = mode
        self.timer_mode = mode
        self._highlight_timer_icons()

    def _highlight_timer_icons(self):
        """Active icon = blue; others = default text color."""
        icon_met = self.root.ids.get("icon_metronome")
        icon_tim = self.root.ids.get("icon_timer")
        icon_swp = self.root.ids.get("icon_stopwatch")
        if not all([icon_met, icon_tim, icon_swp]):
            Clock.schedule_once(lambda dt: self._highlight_timer_icons(), 0)
            return

        default_col = self.theme_cls.text_color
        active_col = self.theme_cls.primary_color

        icon_met.text_color = active_col if self.timer_mode == "metronome" else default_col
        icon_tim.text_color = active_col if self.timer_mode == "timer" else default_col
        icon_swp.text_color = active_col if self.timer_mode == "stopwatch" else default_col

    # -------- Note editor helpers --------
    def focus_note_text(self):
        editor = self.root.ids.sm.get_screen("note_view").ids.note_editor
        editor.focus = True

    def update_open_note_text(self, txt: str):
        self.open_note_body = txt
        note = self._find_note_by_id(self.open_note_id)
        if note and note.get("type") == "note":
            note["content"] = txt

    def _find_note_by_id(self, note_id: str):
        if not note_id:
            return None

        def dfs(node):
            if node.get("id") == note_id:
                return node
            for ch in node.get("children", []):
                found = dfs(ch)
                if found:
                    return found
            return None

        return dfs(self.fs.get("root", {}))


if __name__ == "__main__":
    RCApp().run()
