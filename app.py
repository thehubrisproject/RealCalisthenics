# =============================
# app.py
# =============================

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, DictProperty, ListProperty
from kivymd.app import MDApp
from datetime import datetime

from screens.notes_screen import NotesController

# Dev window
Window.size = (320, 600)
Window.minimum_width = 320
Window.minimum_height = 600


class RCApp(MDApp):
    # app state shared with controllers
    fs = DictProperty({})
    current_path = ListProperty([])  # list of folder ids from root → current
    sort_mode = StringProperty("date")  # 'date' | 'name' | 'type'
    sort_label = StringProperty("Date")
    open_note_title = StringProperty("")
    current_folder_name = StringProperty("")

    def build(self):
        self.title = "RealCalisthenics (Prototype)"
        self.theme_cls.theme_style = "Dark"

        # Load ONLY base.kv (it includes the others and instantiates screens)
        root = Builder.load_file("kv/base.kv")

        # Controllers
        self.notes = NotesController(self)
        return root

    def on_start(self):
        # Seed example FS
        now = datetime.now().isoformat()
        self.fs = {
            "root": {"id": "root", "name": "", "type": "folder", "created": now, "children": [
                {"id": "f1", "name": "Calisthenics", "type": "folder", "created": now, "children": [
                    {"id": "n1", "name": "Planche ideas",
                        "type": "note", "created": now},
                    {"id": "n2", "name": "Front lever drills",
                        "type": "note", "created": now},
                ]},
                {"id": "f2", "name": "Work", "type": "folder",
                    "created": now, "children": []},
                {"id": "n3", "name": "Shopping list",
                    "type": "note", "created": now},
            ]}
        }
        self._set_active_icon("notes")
        self.notes.render_browser()

    # -------- Bottom bar tab switching (safe order) --------
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

    def _set_active_icon(self, name: str):
        notes_icon = self.root.ids.tab_notes
        timer_icon = self.root.ids.tab_timer
        if name == "notes":
            notes_icon.text_color = self.theme_cls.primary_color
            timer_icon.text_color = self.theme_cls.text_color
        else:
            timer_icon.text_color = self.theme_cls.primary_color
            notes_icon.text_color = self.theme_cls.text_color


if __name__ == "__main__":
    RCApp().run()
