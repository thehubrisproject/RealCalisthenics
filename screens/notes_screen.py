# =============================
# screens/notes_screen.py
# =============================
from datetime import datetime
from uuid import uuid4

from kivy.clock import Clock
from widgets.file_tile import FileTile
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField


class NotesController:
    """GoodNotes-style browser: sorting, nav, and create New Note/Folder."""

    def __init__(self, app):
        self.app = app

        # SORT menu
        self._sort_menu = MDDropdownMenu(
            caller=None,
            items=[
                {"text": "Date", "on_release": lambda: self.set_sort("date")},
                {"text": "Name", "on_release": lambda: self.set_sort("name")},
                {"text": "Type", "on_release": lambda: self.set_sort("type")},
            ],
            width_mult=2,
        )

        # ADD menu (for the + button)
        self._add_menu = MDDropdownMenu(
            caller=None,
            items=[
                {"text": "New Note",
                    "on_release": lambda: self._open_name_dialog("note")},
                {"text": "New Folder",
                    "on_release": lambda: self._open_name_dialog("folder")},
            ],
            width_mult=3,
        )

        self._name_dialog = None
        self._name_field = None  # MDTextField while dialog is open

    # ---------- Menus ----------
    def open_sort_menu(self, caller_widget):
        self._sort_menu.caller = caller_widget
        self._sort_menu.open()

    def set_sort(self, mode: str):
        self._sort_menu.dismiss()
        self.app.sort_mode = mode
        self.app.sort_label = "Date" if mode == "date" else "Name" if mode == "name" else "Type"
        self.render_browser()

    def open_add_menu(self, caller_widget):
        self._add_menu.caller = caller_widget
        self._add_menu.open()

    # ---------- Create item dialog ----------
    def _open_name_dialog(self, kind: str):
        # close the dropdown first
        self._add_menu.dismiss()

        # input field
        self._name_field = MDTextField(
            hint_text="Folder name" if kind == "folder" else "Note title",
            text="",
            mode="rectangle",
            size_hint_y=None,
            height="48dp",
        )

        def on_cancel(*_): self._dismiss_name_dialog()
        def on_create(*_): self._do_create(kind)

        self._name_dialog = MDDialog(
            title="Create Folder" if kind == "folder" else "Create Note",
            type="custom",
            content_cls=self._name_field,
            auto_dismiss=False,
            buttons=[
                MDFlatButton(text="Cancel", on_release=on_cancel),
                MDRaisedButton(text="Create", on_release=on_create),
            ],
        )
        self._name_dialog.open()

    def _dismiss_name_dialog(self):
        if self._name_dialog:
            self._name_dialog.dismiss()
            self._name_dialog = None
        Clock.schedule_once(lambda dt: setattr(self, "_name_field", None), 0)

    def _do_create(self, kind: str):
        name_text = self._name_field.text if self._name_field else ""
        self._dismiss_name_dialog()

        name = name_text.strip() or ("Untitled Folder" if kind ==
                                     "folder" else "Untitled Note")

        folder = self._get_current_folder()
        children = folder.setdefault("children", [])
        now = datetime.now().isoformat()

        if kind == "folder":
            new_item = {
                "id": f"f{uuid4().hex[:8]}",
                "name": name,
                "type": "folder",
                "created": now,
                "children": [],
            }
        else:
            new_item = {
                "id": f"n{uuid4().hex[:8]}",
                "name": name,
                "type": "note",
                "created": now,
                "content": "",  # NEW: body storage
            }

        children.append(new_item)
        Clock.schedule_once(lambda dt: self.render_browser(), 0)

    # ---------- FS helpers ----------
    def _get_current_folder(self):
        node = self.app.fs["root"]
        for fid in self.app.current_path:
            for ch in node.get("children", []):
                if ch["id"] == fid and ch["type"] == "folder":
                    node = ch
                    break
        return node

    # ---------- Rendering ----------
    def render_browser(self):
        grid = self.app.root.ids.sm.get_screen('notes').ids.grid
        grid.clear_widgets()

        folder = self._get_current_folder()
        self.app.current_folder_name = folder["name"] if folder["id"] != "root" else ""
        items = list(folder.get("children", []))

        mode = self.app.sort_mode
        if mode == "date":
            items.sort(key=lambda x: x["created"], reverse=True)
        elif mode == "name":
            items.sort(key=lambda x: x["name"].lower())
        else:  # type
            def key_fn(x):
                t_rank = 0 if x["type"] == "folder" else 1
                ts = int(datetime.fromisoformat(x["created"]).timestamp())
                return (t_rank, -ts)
            items.sort(key=key_fn)

        for it in items:
            tile = FileTile(
                item_id=it["id"],
                icon_name="folder-outline" if it["type"] == "folder" else "file-document-outline",
                caption=it["name"],
            )
            tile.bind(on_release=lambda w, _id=it["id"]: self.open_item(_id))
            grid.add_widget(tile)

    # ---------- Navigation ----------
    def open_item(self, item_id: str):
        folder = self._get_current_folder()
        target = None
        for ch in folder.get("children", []):
            if ch["id"] == item_id:
                target = ch
                break
        if not target:
            return

        if target["type"] == "folder":
            self.app.current_path.append(target["id"])
            self.render_browser()
        else:
            # load selected note into app state
            self.app.open_note_id = target["id"]
            self.app.open_note_title = target["name"]
            self.app.open_note_body = target.get("content", "")
            sm = self.app.root.ids.sm
            sm.transition.direction = "left"
            sm.current = "note_view"

    def go_up(self):
        if self.app.current_path:
            self.app.current_path.pop()
            self.render_browser()
