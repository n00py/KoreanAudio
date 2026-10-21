"""Anki integration for Korean Native Audio."""

from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple
from urllib.parse import quote

from anki.collection import OpChanges
from aqt import gui_hooks, mw
from aqt.operations import CollectionOp
from aqt.qt import QAction, QMessageBox, qconnect
from aqt.utils import openLink, showInfo

from .fetch_audio import (
    elevenlabs_audio_filename,
    fetch_audio,
    fetch_from_elevenlabs,
)
from .field_mapping import (
    Settings,
    merge_audio_field,
    resolve_note,
    settings_from_config,
)
from .settings_dialog import show_settings


@dataclass(frozen=True)
class Job:
    note_id: int
    query: str
    destination_field: str


@dataclass
class Outcome:
    changes: Any
    added: int
    skipped: Counter


def fetch_audio_for_current_note() -> None:
    _fetch_note(_active_note())


def _fetch_note(note: Any) -> None:
    if note is None:
        showInfo("No note is currently being edited or reviewed.")
        return
    if not getattr(note, "id", 0):
        showInfo("Add or save this note before fetching its audio.")
        return

    settings = _settings()
    if settings is None:
        return

    job, reason = _job_for_note(note, settings)
    if job:
        _run_jobs(
            [job],
            settings,
            Counter(),
            single_job=job,
            provider="dictionary",
        )
    else:
        showInfo(_skip_message(reason))


def generate_elevenlabs_for_current_note() -> None:
    _generate_elevenlabs_note(_active_note())


def _generate_elevenlabs_note(note: Any) -> None:
    if note is None:
        showInfo("No note is currently being edited or reviewed.")
        return
    if not getattr(note, "id", 0):
        showInfo("Add or save this note before generating its audio.")
        return

    settings = _settings()
    if settings is None or not _require_elevenlabs_key(settings):
        return

    job, reason = _job_for_note(note, settings)
    if job:
        _run_jobs(
            [job],
            settings,
            Counter(),
            single_job=job,
            provider="elevenlabs",
        )
    else:
        showInfo(_skip_message(reason))


def fetch_audio_for_selected_notes(nids: Optional[Sequence[int]] = None) -> None:
    note_ids = list(nids or [])
    if not note_ids:
        showInfo("No notes selected.")
        return

    settings = _settings()
    if settings is None:
        return

    jobs = []
    skipped = Counter()
    for note_id in note_ids:
        job, reason = _job_for_note(mw.col.get_note(note_id), settings)
        if job:
            jobs.append(job)
        else:
            skipped[reason] += 1

    if not jobs:
        _show_summary(0, skipped)
        return

    single_job = jobs[0] if len(note_ids) == 1 else None
    _run_jobs(
        jobs,
        settings,
        skipped,
        single_job=single_job,
        provider="dictionary",
    )


def generate_elevenlabs_for_selected_notes(
    nids: Optional[Sequence[int]] = None,
) -> None:
    note_ids = list(nids or [])
    if not note_ids:
        showInfo("No notes selected.")
        return

    settings = _settings()
    if settings is None or not _require_elevenlabs_key(settings):
        return

    jobs = []
    skipped = Counter()
    for note_id in note_ids:
        job, reason = _job_for_note(mw.col.get_note(note_id), settings)
        if job:
            jobs.append(job)
        else:
            skipped[reason] += 1

    if not jobs:
        _show_summary(0, skipped, provider="elevenlabs")
        return

    single_job = jobs[0] if len(note_ids) == 1 else None
    _run_jobs(
        jobs,
        settings,
        skipped,
        single_job=single_job,
        provider="elevenlabs",
    )


def _require_elevenlabs_key(settings: Settings) -> bool:
    if settings.elevenlabs_api_key:
        return True
    showInfo(
        "Add your ElevenLabs API key in Tools → Korean Native Audio "
        "Settings… before generating Anna audio."
    )
    return False


def _settings() -> Optional[Settings]:
    try:
        return settings_from_config(mw.addonManager.getConfig(__name__))
    except ValueError as error:
        showInfo("Korean Native Audio configuration error:\n\n{}".format(error))
        return None


def _job_for_note(
    note: Any,
    settings: Settings,
) -> Tuple[Optional[Job], Optional[str]]:
    resolution = resolve_note(note, settings.field_mappings)
    if resolution.target is None:
        return None, resolution.reason

    return (
        Job(
            note_id=int(note.id),
            query=resolution.target.query,
            destination_field=resolution.target.destination_field,
        ),
        None,
    )


def _run_jobs(
    jobs: Sequence[Job],
    settings: Settings,
    initially_skipped: Counter,
    single_job: Optional[Job],
    provider: str,
) -> None:
    operation = CollectionOp(
        parent=mw,
        op=lambda collection: _fetch_and_apply(
            collection,
            jobs,
            settings.overwrite_existing,
            settings.krdict_api_key,
            settings.forvo_api_key,
            settings.elevenlabs_api_key,
            provider,
        ),
    )
    operation.success(
        lambda outcome: _finish(
            outcome,
            initially_skipped,
            single_job,
            settings,
            provider,
        )
    )
    operation.run_in_background()


def _fetch_and_apply(
    collection: Any,
    jobs: Sequence[Job],
    overwrite_existing: bool,
    krdict_api_key: str,
    forvo_api_key: str,
    elevenlabs_api_key: str,
    provider: str,
) -> Outcome:
    changed_notes = []
    skipped = Counter()
    audio_cache = {}

    for job in jobs:
        note = collection.get_note(job.note_id)
        if job.destination_field not in set(note.keys()):
            skipped["stale_note"] += 1
            continue
        current_value = note[job.destination_field]

        if provider == "elevenlabs":
            predicted_tag = "[sound:{}]".format(
                elevenlabs_audio_filename(job.query)
            )
            if predicted_tag in str(current_value):
                skipped["duplicate_audio"] += 1
                continue

        if job.query not in audio_cache:
            if provider == "elevenlabs":
                audio_cache[job.query] = fetch_from_elevenlabs(
                    job.query,
                    elevenlabs_api_key,
                )
            else:
                audio_cache[job.query] = fetch_audio(
                    job.query,
                    krdict_api_key=krdict_api_key,
                    forvo_api_key=forvo_api_key,
                )
        audio = audio_cache[job.query]
        if audio is None:
            skipped[
                "elevenlabs_failed" if provider == "elevenlabs" else "not_found"
            ] += 1
            continue

        filename = collection.media.write_data(audio.filename, audio.data)
        merged_value = merge_audio_field(
            current_value,
            "[sound:{}]".format(filename),
            replace_existing=overwrite_existing,
        )
        if merged_value == str(current_value).strip():
            skipped["duplicate_audio"] += 1
            continue
        note[job.destination_field] = merged_value
        changed_notes.append(note)

    changes = collection.update_notes(changed_notes) if changed_notes else OpChanges()
    return Outcome(changes=changes, added=len(changed_notes), skipped=skipped)


def _finish(
    outcome: Outcome,
    initially_skipped: Counter,
    single_job: Optional[Job],
    settings: Settings,
    provider: str,
) -> None:
    skipped = Counter(initially_skipped)
    skipped.update(outcome.skipped)

    if single_job is not None:
        if outcome.added:
            verb = "Generated Anna audio" if provider == "elevenlabs" else "Fetched audio"
            showInfo("{} for: {}".format(verb, single_job.query))
        elif skipped["not_found"] and provider == "dictionary":
            _prompt_audio_fallbacks(single_job, settings)
        else:
            showInfo(_skip_message(_first_reason(skipped)))
        return

    _show_summary(outcome.added, skipped, provider=provider)


def _show_summary(
    added: int,
    skipped: Counter,
    provider: str = "dictionary",
) -> None:
    action = "Anna audio generated" if provider == "elevenlabs" else "Audio added"
    lines = [
        "{}: {} notes".format(action, added),
        "Skipped: {} notes".format(sum(skipped.values())),
    ]
    labels = (
        ("no_mapping", "configured fields not found"),
        ("empty_source", "source field empty"),
        ("duplicate_audio", "same audio already present"),
        ("not_found", "no audio found"),
        ("elevenlabs_failed", "ElevenLabs generation failed"),
        ("stale_note", "note changed while fetching"),
    )
    lines.extend(
        "  - {}: {}".format(label, skipped[key])
        for key, label in labels
        if skipped[key]
    )
    showInfo("\n".join(lines))


def _skip_message(reason: Optional[str]) -> str:
    messages = {
        "no_mapping": (
            "This note has no configured source/destination field pair. "
            "Open Tools → Korean Native Audio Settings… to add one."
        ),
        "empty_source": "All configured source fields on this note are empty.",
        "duplicate_audio": "The same audio is already in the destination field.",
        "elevenlabs_failed": (
            "ElevenLabs could not generate audio. Check the API key, account "
            "quota, and network connection."
        ),
        "stale_note": "The note changed while audio was being fetched.",
    }
    return messages.get(reason, "No audio was added.")


def _first_reason(skipped: Counter) -> Optional[str]:
    return next((reason for reason, count in skipped.items() if count), None)


def _active_note() -> Any:
    active_window = mw.app.activeWindow()
    editor = getattr(active_window, "editor", None)
    if getattr(editor, "note", None) is not None:
        return editor.note

    reviewer = getattr(mw, "reviewer", None)
    card = getattr(reviewer, "card", None)
    if active_window is mw and card is not None:
        return card.note()

    for window in mw.app.topLevelWidgets():
        editor = getattr(window, "editor", None)
        if getattr(editor, "note", None) is not None:
            return editor.note
    return card.note() if card is not None else None


def _prompt_audio_fallbacks(job: Job, settings: Settings) -> None:
    dialog = QMessageBox(mw)
    dialog.setIcon(_qt_enum(QMessageBox, "Icon", "Information"))
    dialog.setWindowTitle("No Audio Found Automatically")
    dialog.setText("No dictionary audio was found for '{}'.".format(job.query))
    dialog.setInformativeText(
        "Generate clear-slow Anna Kim audio with ElevenLabs, or open the "
        "Korean Forvo page for manual download."
    )
    elevenlabs_button = dialog.addButton(
        "Generate with ElevenLabs",
        _qt_enum(QMessageBox, "ButtonRole", "AcceptRole"),
    )
    open_button = dialog.addButton(
        "Open Forvo",
        _qt_enum(QMessageBox, "ButtonRole", "ActionRole"),
    )
    dialog.addButton(_qt_enum(QMessageBox, "StandardButton", "Cancel"))
    dialog.setDefaultButton(elevenlabs_button)
    (getattr(dialog, "exec", None) or dialog.exec_)()
    clicked = dialog.clickedButton()
    if clicked is elevenlabs_button:
        if _require_elevenlabs_key(settings):
            _run_jobs(
                [job],
                settings,
                Counter(),
                single_job=job,
                provider="elevenlabs",
            )
        else:
            open_settings()
    elif clicked is open_button:
        openLink(
            "https://forvo.com/word/{}/#ko".format(
                quote(job.query, safe="")
            )
        )


def _qt_enum(owner: Any, group: str, name: str) -> Any:
    return getattr(getattr(owner, group, owner), name)


def open_settings() -> None:
    show_settings(mw, mw.addonManager, __name__)


def add_menu_items() -> None:
    fetch_action = QAction("Fetch Korean Audio for Current Note", mw)
    qconnect(fetch_action.triggered, fetch_audio_for_current_note)
    mw.form.menuTools.addAction(fetch_action)

    elevenlabs_action = QAction(
        "Generate ElevenLabs Korean Audio for Current Note",
        mw,
    )
    qconnect(
        elevenlabs_action.triggered,
        generate_elevenlabs_for_current_note,
    )
    mw.form.menuTools.addAction(elevenlabs_action)

    settings_action = QAction("Korean Native Audio Settings…", mw)
    qconnect(settings_action.triggered, open_settings)
    mw.form.menuTools.addAction(settings_action)


def add_editor_button(buttons: list, editor: Any) -> None:
    buttons.append(
        editor.addButton(
            icon=None,
            cmd="korean_native_audio_fetch",
            func=lambda active_editor: _fetch_note(active_editor.note),
            tip="Fetch Korean pronunciation audio (Ctrl+Shift+K)",
            label="🔊 Korean",
            id="korean-native-audio",
            keys="Ctrl+Shift+K",
        )
    )
    buttons.append(
        editor.addButton(
            icon=None,
            cmd="korean_native_audio_elevenlabs",
            func=lambda active_editor: _generate_elevenlabs_note(
                active_editor.note
            ),
            tip=(
                "Generate clear-slow Anna Kim Korean audio with ElevenLabs "
                "(Ctrl+Shift+E)"
            ),
            label="✨ ElevenLabs",
            id="korean-native-audio-elevenlabs",
            keys="Ctrl+Shift+E",
        )
    )


def on_browser_context_menu(browser: Any, menu: Any) -> None:
    selected_notes = getattr(browser, "selected_notes", None)
    callback = selected_notes or browser.selectedNotes

    action = QAction("Fetch Korean Audio for Selected Notes", menu)
    qconnect(action.triggered, lambda: fetch_audio_for_selected_notes(callback()))

    elevenlabs_action = QAction(
        "Generate ElevenLabs Korean Audio for Selected Notes",
        menu,
    )
    qconnect(
        elevenlabs_action.triggered,
        lambda: generate_elevenlabs_for_selected_notes(callback()),
    )
    menu.addSeparator()
    menu.addAction(action)
    menu.addAction(elevenlabs_action)


gui_hooks.main_window_did_init.append(add_menu_items)
gui_hooks.editor_did_init_buttons.append(add_editor_button)
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)
mw.addonManager.setConfigAction(__name__, open_settings)
