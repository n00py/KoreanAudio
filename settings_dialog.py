"""Friendly configuration window for Korean Native Audio."""

from typing import Any, Mapping, Optional, Sequence

from aqt.qt import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import showWarning

from .field_mapping import Settings, settings_from_config


class SettingsDialog(QDialog):
    """Edit all supported settings without exposing Anki's JSON editor."""

    def __init__(
        self,
        parent: Any,
        config: Optional[Mapping[str, Any]],
    ) -> None:
        super().__init__(parent)
        self.saved_config = None
        self._base_config = dict(config or {})
        settings = settings_from_config(config)

        self.setWindowTitle("Korean Native Audio Settings")
        self.setMinimumSize(680, 480)

        layout = QVBoxLayout(self)
        introduction = QLabel(
            "Choose which note fields contain Korean text and where the "
            "downloaded audio should be saved. Mappings are tried from top "
            "to bottom."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        mapping_group = QGroupBox("Note field mappings")
        mapping_layout = QVBoxLayout(mapping_group)
        mapping_help = QLabel(
            "Click a cell to edit it. If several input fields are listed, the "
            "first non-empty one is used."
        )
        mapping_help.setWordWrap(True)
        mapping_layout.addWidget(mapping_help)

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(
            ("Read Korean from (comma-separated)", "Save audio to")
        )
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setSelectionBehavior(
            _enum(QAbstractItemView, "SelectionBehavior", "SelectRows")
        )
        self.mapping_table.setSelectionMode(
            _enum(QAbstractItemView, "SelectionMode", "SingleSelection")
        )
        self.mapping_table.setEditTriggers(
            _enum(QAbstractItemView, "EditTrigger", "AllEditTriggers")
        )
        header = self.mapping_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            _enum(QHeaderView, "ResizeMode", "Stretch"),
        )
        header.setSectionResizeMode(
            1,
            _enum(QHeaderView, "ResizeMode", "Stretch"),
        )
        mapping_layout.addWidget(self.mapping_table)

        mapping_buttons = QHBoxLayout()
        add_button = QPushButton("Add mapping")
        remove_button = QPushButton("Remove")
        up_button = QPushButton("Move up")
        down_button = QPushButton("Move down")
        qconnect(add_button.clicked, lambda: self._add_mapping())
        qconnect(remove_button.clicked, self._remove_mapping)
        qconnect(up_button.clicked, lambda: self._move_mapping(-1))
        qconnect(down_button.clicked, lambda: self._move_mapping(1))
        mapping_buttons.addWidget(add_button)
        mapping_buttons.addWidget(remove_button)
        mapping_buttons.addStretch()
        mapping_buttons.addWidget(up_button)
        mapping_buttons.addWidget(down_button)
        mapping_layout.addLayout(mapping_buttons)
        layout.addWidget(mapping_group)

        existing_layout = QHBoxLayout()
        existing_layout.addWidget(QLabel("If the destination already has content:"))
        self.existing_content_behavior = QComboBox()
        self.existing_content_behavior.addItems(
            (
                "Append new audio (recommended)",
                "Replace existing content",
            )
        )
        existing_layout.addWidget(self.existing_content_behavior)
        existing_layout.addStretch()
        layout.addLayout(existing_layout)

        api_group = QGroupBox("Optional dictionary API keys")
        api_layout = QFormLayout(api_group)
        api_help = QLabel(
            "Source order: Naver → KRDICT (when configured) → Forvo API "
            "(when configured) → public Forvo fallback."
        )
        api_help.setWordWrap(True)
        api_layout.addRow(api_help)

        self.krdict_key = QLineEdit()
        self.krdict_key.setPlaceholderText("Optional 32-character KRDICT key")
        self.forvo_key = QLineEdit()
        self.forvo_key.setPlaceholderText("Optional Forvo API key")
        api_layout.addRow("KRDICT API key:", self.krdict_key)
        api_layout.addRow("Forvo API key:", self.forvo_key)

        self.show_keys_checkbox = QCheckBox("Show API keys")
        qconnect(self.show_keys_checkbox.toggled, self._set_keys_visible)
        api_layout.addRow("", self.show_keys_checkbox)
        local_note = QLabel(
            "Keys are stored in this Anki installation's local add-on settings."
        )
        local_note.setWordWrap(True)
        api_layout.addRow(local_note)
        layout.addWidget(api_group)

        buttons = QDialogButtonBox()
        reset_button = buttons.addButton(
            "Restore defaults",
            _enum(QDialogButtonBox, "ButtonRole", "ResetRole"),
        )
        save_button = buttons.addButton(
            "Save",
            _enum(QDialogButtonBox, "ButtonRole", "AcceptRole"),
        )
        cancel_button = buttons.addButton(
            "Cancel",
            _enum(QDialogButtonBox, "ButtonRole", "RejectRole"),
        )
        save_button.setDefault(True)
        qconnect(reset_button.clicked, self._restore_defaults)
        qconnect(save_button.clicked, self._save)
        qconnect(cancel_button.clicked, self.reject)
        layout.addWidget(buttons)

        self._load(settings)

    def _load(self, settings: Settings) -> None:
        self.mapping_table.setRowCount(0)
        for mapping in settings.field_mappings:
            self._add_mapping(
                mapping.source_fields,
                mapping.destination_field,
            )
        self.existing_content_behavior.setCurrentIndex(
            1 if settings.overwrite_existing else 0
        )
        self.krdict_key.setText(settings.krdict_api_key)
        self.forvo_key.setText(settings.forvo_api_key)
        self.show_keys_checkbox.setChecked(False)
        self._set_keys_visible(False)

    def _add_mapping(
        self,
        source_fields: Sequence[str] = (),
        destination_field: str = "",
    ) -> None:
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        self.mapping_table.setItem(
            row,
            0,
            QTableWidgetItem(", ".join(source_fields)),
        )
        self.mapping_table.setItem(
            row,
            1,
            QTableWidgetItem(destination_field),
        )
        self.mapping_table.selectRow(row)

    def _remove_mapping(self) -> None:
        row = self.mapping_table.currentRow()
        if row >= 0:
            self.mapping_table.removeRow(row)

    def _move_mapping(self, offset: int) -> None:
        row = self.mapping_table.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.mapping_table.rowCount():
            return

        current = [self._cell_text(row, column) for column in range(2)]
        other = [self._cell_text(target, column) for column in range(2)]
        for column in range(2):
            self.mapping_table.setItem(row, column, QTableWidgetItem(other[column]))
            self.mapping_table.setItem(
                target,
                column,
                QTableWidgetItem(current[column]),
            )
        self.mapping_table.selectRow(target)

    def _set_keys_visible(self, visible: bool) -> None:
        mode_name = "Normal" if visible else "Password"
        mode = _enum(QLineEdit, "EchoMode", mode_name)
        self.krdict_key.setEchoMode(mode)
        self.forvo_key.setEchoMode(mode)

    def _restore_defaults(self) -> None:
        self._load(settings_from_config(None))

    def _save(self) -> None:
        try:
            self.saved_config = self._config_from_form()
        except ValueError as error:
            showWarning(
                "Please fix the settings:\n\n{}".format(error),
                parent=self,
                title="Korean Native Audio",
            )
            return
        self.accept()

    def _config_from_form(self) -> dict:
        if self.mapping_table.rowCount() == 0:
            raise ValueError("Add at least one note field mapping.")

        mappings = []
        for row in range(self.mapping_table.rowCount()):
            source_fields = list(
                dict.fromkeys(
                    field.strip()
                    for field in self._cell_text(row, 0).split(",")
                    if field.strip()
                )
            )
            destination = self._cell_text(row, 1).strip()
            if not source_fields:
                raise ValueError(
                    "Mapping {} needs at least one input field.".format(row + 1)
                )
            if not destination:
                raise ValueError(
                    "Mapping {} needs an audio destination field.".format(row + 1)
                )
            mappings.append(
                {
                    "source_fields": source_fields,
                    "destination_field": destination,
                }
            )

        config = dict(self._base_config)
        config.update(
            {
                "field_mappings": mappings,
                "overwrite_existing": (
                    self.existing_content_behavior.currentIndex() == 1
                ),
                "krdict_api_key": self.krdict_key.text().strip(),
                "forvo_api_key": self.forvo_key.text().strip(),
            }
        )
        settings_from_config(config)
        return config

    def _cell_text(self, row: int, column: int) -> str:
        item = self.mapping_table.item(row, column)
        return item.text() if item is not None else ""


def show_settings(parent: Any, manager: Any, module_name: str) -> None:
    """Open the friendly editor and persist only when the user presses Save."""
    config = manager.getConfig(module_name) or {}
    try:
        dialog = SettingsDialog(parent, config)
    except ValueError as error:
        showWarning(
            "The existing settings could not be read:\n\n{}\n\n"
            "Defaults will be shown so you can repair them.".format(error),
            parent=parent,
            title="Korean Native Audio",
        )
        dialog = SettingsDialog(parent, {})

    (getattr(dialog, "exec", None) or dialog.exec_)()
    if dialog.saved_config is not None:
        manager.writeConfig(module_name, dialog.saved_config)


def _enum(owner: Any, group: str, name: str) -> Any:
    """Return an enum value on both Qt 5 and Qt 6."""
    return getattr(getattr(owner, group, owner), name)
