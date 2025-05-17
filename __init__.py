from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo
from aqt import gui_hooks
from .fetch_audio import fetch_and_save_audio
import os

def fetch_audio_for_current_note():
    editor = mw.form.currentEditor
    if not editor or not editor.note:
        showInfo("No note is currently being edited.")
        return

    note = editor.note
    model_fields = [fld['name'] for fld in note.model()['flds']]
    try:
        korean_idx = model_fields.index("Korean")
        sound_idx = model_fields.index("Sound")
    except ValueError:
        showInfo("This note type must have 'Korean' and 'Sound' fields.")
        return

    korean = note.fields[korean_idx].strip()
    if not korean:
        showInfo("Korean field is empty.")
        return

    filepath = fetch_and_save_audio(korean)
    if not filepath:
        showInfo(f"No audio found for: {korean}")
        return

    filename = os.path.basename(filepath)
    note.fields[sound_idx] = f"[sound:{filename}]"
    note.flush()
    mw.col.media.addFile(filepath)
    showInfo(f"Fetched audio for: {korean}")

def fetch_audio_for_selected_notes(nids=None):
    if not nids:
        showInfo("No notes selected.")
        return

    mw.progress.start(label="Fetching Korean audio...", immediate=True)
    success = 0
    fail = 0
    for nid in nids:
        note = mw.col.get_note(nid)
        model_fields = [fld['name'] for fld in note.model()['flds']]
        try:
            korean_idx = model_fields.index("Korean")
            sound_idx = model_fields.index("Sound")
        except ValueError:
            continue

        korean = note.fields[korean_idx].strip()
        if not korean:
            continue

        filepath = fetch_and_save_audio(korean)
        if filepath:
            filename = os.path.basename(filepath)
            note.fields[sound_idx] = f"[sound:{filename}]"
            mw.col.media.addFile(filepath)
            note.flush()
            success += 1
        else:
            fail += 1
    mw.progress.finish()
    showInfo(f"✅ Audio added: {success} notes\n❌ Skipped: {fail} (no audio found)")

def add_menu_items():
    action_one = QAction("Fetch Korean Audio for Current Note", mw)
    action_one.triggered.connect(fetch_audio_for_current_note)
    mw.form.menuTools.addAction(action_one)

gui_hooks.main_window_did_init.append(add_menu_items)

def on_browser_context_menu(browser, menu):
    action = QAction("Fetch Korean Audio for Selected Notes", menu)
    action.triggered.connect(lambda: fetch_audio_for_selected_notes(browser.selected_notes()))
    menu.addSeparator()
    menu.addAction(action)

gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)
