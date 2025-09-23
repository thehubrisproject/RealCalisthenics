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
    current_folder_name = StringProperty("")

    # open note state
    open_note_id = StringProperty("")
    open_note_title = StringProperty("")
    open_note_body = StringProperty("")

    def build(self):
        self.title = "RealCalisthenics (Prototype)"
        self.theme_cls.theme_style = "Dark"

        # Load ONLY base.kv (includes define + instantiate screens)
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
                        "type": "note", "created": now, "content": ""},
                    {"id": "n2", "name": "Front lever drills",
                        "type": "note", "created": now, "content": ""},
                ]},
                {"id": "f2", "name": "Work", "type": "folder",
                    "created": now, "children": []},
                {"id": "n3", "name": "Shopping list",
                    "type": "note", "created": now, "content": ""},
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

    # -------- Note editor plumbing --------
    def focus_note_text(self):
        """Focus the editor when the T button is pressed."""
        try:
            editor = self.root.ids.sm.get_screen('note_view').ids.note_editor
            editor.focus = True
        except Exception:
            pass

    def update_open_note_text(self, txt: str):
        """Update app state and the underlying note object as user types."""
        self.open_note_body = txt
        # find current note object and persist in memory
        note = self._find_note_by_id(self.open_note_id)
        if note and note.get("type") == "note":
            note["content"] = txt

    def _find_note_by_id(self, note_id: str):
        """Depth-first search through the fs tree to find a note by id."""
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
