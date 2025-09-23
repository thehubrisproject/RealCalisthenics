# =============================
# widgets/file_tile.py
# =============================
from kivymd.uix.card import MDCard
from kivy.properties import StringProperty


class FileTile(MDCard):
    item_id = StringProperty("")
    icon_name = StringProperty("file-document-outline")
    caption = StringProperty("")
