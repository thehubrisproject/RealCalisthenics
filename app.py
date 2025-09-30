# app.py
from datetime import datetime
from time import perf_counter
import os
import wave
import struct
import math

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    StringProperty,
    DictProperty,
    ListProperty,
    NumericProperty,
    BooleanProperty,
)
from kivy.uix.widget import Widget
# Wheels
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.label import MDLabel
from kivymd.app import MDApp

from math import atan2, degrees

from screens.notes_screen import NotesController

# Dev window size
Window.size = (320, 600)
Window.minimum_width = 320
Window.minimum_height = 600


# ---------------------------
# Metronome Dial
# ---------------------------
class MetronomeDial(Widget):
    """Rotatable dial: 1 BPM per 22.5 degrees (1/16 of a full turn)."""
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
        ang = degrees(atan2(dy, dx))
        if ang < 0:
            ang += 360
        return ang

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
        d = ang - self._last_ang
        if d > 180:
            d -= 360
        elif d <= -180:
            d += 360

        self._accum_deg -= d
        self._last_ang = ang

        step_deg = 22.5
        bpm_delta = int(round(self._accum_deg / step_deg))

        app = MDApp.get_running_app()
        new_bpm = max(30, min(300, self._start_bpm + bpm_delta))
        if new_bpm != app.bpm:
            app.bpm = new_bpm

        self.angle = app.bpm * step_deg
        return True

    def on_touch_up(self, touch):
        if self._dragging:
            self._dragging = False
            return True
        return super().on_touch_up(touch)


# ---------------------------
# iOS-style NumberWheel
#  - exact centering
#  - momentum-snap
#  - tap-to-select (fixed: no vertical mirroring)
# ---------------------------
class NumberWheel(ScrollView):
    values = ListProperty([])
    value_index = NumericProperty(0)
    unit = StringProperty("")   # "hours" | "min" | "sec"

    ROW_H = dp(36)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self.bar_width = 0
        self.effect_cls = "ScrollEffect"

        self._box = BoxLayout(orientation="vertical",
                              size_hint_y=None, spacing=0)
        self.add_widget(self._box)

        # rebuild triggers
        self.bind(size=lambda *_: Clock.schedule_once(self._rebuild, 0))
        self.bind(values=lambda *_: Clock.schedule_once(self._rebuild, 0))

        # interaction flags
        self._built = False
        self._touch_active = False
        self._touch_scrolled = False
        self._start_scroll_y = None

        # momentum snap watcher
        self._snap_ev = None
        self._vel_threshold = 5.0  # lower = waits longer before snapping

    # spacer so a row aligns with the visual center
    def _center_pad(self):
        return (self.height - self.ROW_H) / 2.0 if self.height else dp(40)

    def on_value_index(self, *_):
        pass

    # ---------- touch handling ----------
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_active = True
            self._touch_scrolled = False
            self._start_scroll_y = self.scroll_y
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._touch_active and self.collide_point(*touch.pos):
            if abs(self.scroll_y - (self._start_scroll_y or self.scroll_y)) > 0.003:
                self._touch_scrolled = True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._touch_active:
            self._touch_active = False
            if not self._touch_scrolled:
                # tap -> snap to the exact row you tapped (corrected for coord system)
                idx = self._index_from_touch(touch)
                self._scroll_to_index(idx, animate=True)
            else:
                # drag release -> wait for momentum to slow, then snap to nearest
                self._begin_momentum_snap()
        return super().on_touch_up(touch)

    # ---------- momentum snap ----------
    def _begin_momentum_snap(self):
        if self._snap_ev:
            self._snap_ev.cancel()
            self._snap_ev = None

        eff = getattr(self, "effect_y", None)
        if eff is None:
            self._snap_to_nearest()
            return

        self._snap_ev = Clock.schedule_interval(self._check_snap_ready, 0)

    def _check_snap_ready(self, dt):
        eff = getattr(self, "effect_y", None)
        if eff is None:
            self._snap_to_nearest()
            return False
        vel = abs(float(getattr(eff, "velocity", 0.0)) or 0.0)
        if vel < self._vel_threshold:
            if self._snap_ev:
                self._snap_ev.cancel()
                self._snap_ev = None
            self._snap_to_nearest()
            return False
        return True

    # ---------- internals ----------
    def _rebuild(self, *_):
        self._box.clear_widgets()
        if not self.values:
            return

        pad = self._center_pad()
        # top/bottom spacers so a row can sit at the visual center line
        self._box.add_widget(BoxLayout(size_hint_y=None, height=pad))
        for s in self.values:
            self._box.add_widget(
                MDLabel(
                    text=s,
                    halign="center",
                    size_hint_y=None,
                    height=self.ROW_H,
                    theme_text_color="Custom",
                    text_color=(1, 1, 1, 1),
                    font_size="20sp",
                )
            )
        self._box.add_widget(BoxLayout(size_hint_y=None, height=pad))
        self._box.height = pad * 2 + len(self.values) * self.ROW_H
        self._built = True
        Clock.schedule_once(lambda dt: self._scroll_to_index(
            self.value_index, animate=False), 0)

    def _index_from_scroll(self):
        """Nearest row whose center is closest to the viewport center."""
        if not self._built or not self.values:
            return 0
        content_h = self._box.height
        view_h = self.height
        if content_h <= view_h:
            return 0

        top_to_view_top = (1 - self.scroll_y) * (content_h - view_h)
        y_center = top_to_view_top + view_h / 2.0
        pad = self._center_pad()

        y_rel = y_center - (pad + self.ROW_H / 2.0)
        idx = int(round(y_rel / self.ROW_H))
        return max(0, min(len(self.values) - 1, idx))

    def _index_from_touch(self, touch):
        """Map a tap Y to the nearest row index (fixed: bottom-origin -> top-origin)."""
        if not self._built or not self.values or not self.collide_point(*touch.pos):
            return self.value_index

        # local y within widget (0 at bottom)
        local_y = touch.y - self.y

        content_h = self._box.height
        view_h = self.height
        if content_h <= view_h:
            return self.value_index

        # distance from content top to top of viewport
        top_to_view_top = (1 - self.scroll_y) * (content_h - view_h)

        # convert local_y (bottom-origin) to distance from the top of the viewport
        y_from_view_top = view_h - local_y

        # absolute content y where the tap occurred
        y_content = top_to_view_top + y_from_view_top

        pad = self._center_pad()
        y_rel = y_content - (pad + self.ROW_H / 2.0)
        idx = int(round(y_rel / self.ROW_H))
        return max(0, min(len(self.values) - 1, idx))

    def _scroll_to_index(self, idx: int, animate=True):
        if not self._built:
            return
        idx = max(0, min(len(self.values) - 1, idx))

        content_h = self._box.height
        view_h = self.height
        if content_h <= view_h:
            return

        pad = self._center_pad()
        # absolute Y (content coords) of target row center
        y_target = pad + idx * self.ROW_H + self.ROW_H / 2.0
        # top-of-viewport so its center hits y_target
        top_to_view_top = y_target - view_h / 2.0
        top_to_view_top = max(0.0, min(content_h - view_h, top_to_view_top))
        target_scroll_y = 1.0 - (top_to_view_top / (content_h - view_h))

        from kivy.animation import Animation
        if animate:
            Animation.cancel_all(self, "scroll_y")
            Animation(scroll_y=target_scroll_y, d=0.12,
                      t="out_quart").start(self)
        else:
            self.scroll_y = target_scroll_y

        self.value_index = idx

    def _snap_to_nearest(self, *_):
        idx = self._index_from_scroll()
        self._scroll_to_index(idx, animate=True)


# ---------------------------
# App
# ---------------------------
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

    # Timer picker state (H/M/S wheels)
    t_hours = NumericProperty(0)
    t_minutes = NumericProperty(0)
    t_seconds = NumericProperty(0)

    # Internal metronome fields (audio + scheduling)
    _met_event = None
    _tick_hi = None
    _tick_lo = None
    _beat_index = 0
    _last_tick_ts = None  # perf_counter() time of the last tick

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
        # Sync dial visual to current BPM at startup
        Clock.schedule_once(self._sync_dial_angle, 0)

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
        self._ensure_click_sounds()
        self.is_metronome_running = True
        self._beat_index = 0
        self._metronome_tick(0)  # first tick immediately

    def stop_metronome(self):
        self.is_metronome_running = False
        if self._met_event is not None:
            self._met_event.cancel()
            self._met_event = None

    def _set_active_icon(self, name: str):
        notes_icon = self.root.ids.tab_notes
        timer_icon = self.root.ids.tab_timer
        if name == "notes":
            notes_icon.text_color = self.theme_cls.primary_color
            timer_icon.text_color = self.theme_cls.text_color
        else:
            timer_icon.text_color = self.theme_cls.primary_color
            notes_icon.text_color = self.theme_cls.text_color

    def on_bpm(self, *_):
        self._sync_dial_angle()
        if not self.is_metronome_running:
            return
        if self._last_tick_ts is None:
            self._schedule_next_tick()
            return
        elapsed = perf_counter() - self._last_tick_ts
        new_interval = max(60.0 / float(max(1, self.bpm)), 0.001)
        remaining = max(0.001, new_interval - elapsed)
        self._schedule_next_tick(delay=remaining)

    # -------- Metronome audio --------
    def _ensure_click_sounds(self):
        if self._tick_hi and self._tick_lo:
            return
        hi_path = os.path.join(os.getcwd(), "rc_tick_hi.wav")
        lo_path = os.path.join(os.getcwd(), "rc_tick_lo.wav")
        if not os.path.exists(hi_path):
            self._sine_click(hi_path, freq=1200, ms=40, vol=0.35)
        if not os.path.exists(lo_path):
            self._sine_click(lo_path, freq=800, ms=40, vol=0.35)
        self._tick_hi = SoundLoader.load(hi_path)
        self._tick_lo = SoundLoader.load(lo_path)

    def _sine_click(self, path, freq=1000, ms=40, vol=0.3, sr=44100):
        frames = int(sr * ms / 1000.0)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            for n in range(frames):
                t = n / sr
                env = 0.5 * (1 - math.cos(2 * math.pi *
                             (n / (frames - 1)))) if frames > 1 else 1.0
                val = vol * env * math.sin(2 * math.pi * freq * t)
                wf.writeframesraw(struct.pack(
                    "<h", int(max(-1, min(1, val)) * 32767)))
            wf.writeframes(b"")

    def _schedule_next_tick(self, delay=None):
        if self._met_event is not None:
            self._met_event.cancel()
            self._met_event = None
        if delay is None:
            delay = max(60.0 / float(max(1, self.bpm)), 0.001)
        self._met_event = Clock.schedule_once(self._metronome_tick, delay)

    def _metronome_tick(self, dt):
        if not self.is_metronome_running or not (self._tick_hi and self._tick_lo):
            return
        if self._beat_index % 2 == 0:
            self._tick_hi.stop()
            self._tick_hi.play()
        else:
            self._tick_lo.stop()
            self._tick_lo.play()
        self._beat_index += 1
        self._last_tick_ts = perf_counter()
        self._schedule_next_tick()

    # -------- Metronome dial Helper --------
    def _sync_dial_angle(self, *args):
        try:
            dial = (
                self.root.ids.sm.get_screen("timer")
                .ids.timer_modes.get_screen("metronome")
                .ids.met_dial
            )
            dial.angle = self.bpm * 22.5
        except Exception:
            pass

    # -------- Timer sub-mode (Metronome / Timer / Stopwatch) --------
    def switch_timer_mode(self, mode: str):
        order = ["metronome", "timer", "stopwatch"]
        if mode not in order:
            raise ValueError(f"Unknown timer mode: {mode}")

        modes = self.root.ids.get("timer_modes")
        if modes is None:
            Clock.schedule_once(lambda dt: self.switch_timer_mode(mode), 0)
            return

        current = self.timer_mode if self.timer_mode in order else "metronome"

        if order.index(mode) > order.index(current):
            modes.transition.direction = "left"
        elif order.index(mode) < order.index(current):
            modes.transition.direction = "right"
        modes.transition.duration = 0.20

        modes.current = mode
        self.timer_mode = mode
        self._highlight_timer_icons()

    def _highlight_timer_icons(self):
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
