# Project layout
#
# realcalisthenics/
# ├─ app.py                  # RCApp entry point (theme, screens, tab switching)
# ├─ screens/
# │  └─ notes_screen.py      # NotesController: render/sort/nav for the file browser
# ├─ widgets/
# │  └─ file_tile.py         # FileTile widget used for folders/notes
# └─ kv/
#    ├─ base.kv              # Root layout: ScreenManager + bottom bar
#    ├─ notes.kv             # FileHeader and grid container for the browser
#    └─ note_view.kv         # Blank note screen