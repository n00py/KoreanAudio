"""Resolve configurable Anki note fields without depending on Anki."""

import re
from typing import Any, Mapping, NamedTuple, Optional, Sequence, Tuple


class FieldMapping(NamedTuple):
    source_fields: Tuple[str, ...]
    destination_field: str


class Settings(NamedTuple):
    field_mappings: Tuple[FieldMapping, ...]
    overwrite_existing: bool
    krdict_api_key: str
    forvo_api_key: str


class NoteTarget(NamedTuple):
    query: str
    source_field: str
    destination_field: str


class Resolution(NamedTuple):
    target: Optional[NoteTarget]
    reason: Optional[str]


DEFAULT_MAPPINGS = (
    FieldMapping(source_fields=("Korean",), destination_field="Sound"),
)


def settings_from_config(config: Optional[Mapping[str, Any]]) -> Settings:
    """Validate Anki config and return immutable settings."""
    config = config or {}
    raw_mappings = config.get("field_mappings")
    if raw_mappings is None:
        mappings = DEFAULT_MAPPINGS
    else:
        if not isinstance(raw_mappings, list) or not raw_mappings:
            raise ValueError("'field_mappings' must be a non-empty list.")
        mappings = tuple(
            _parse_mapping(item, index)
            for index, item in enumerate(raw_mappings)
        )

    overwrite = config.get("overwrite_existing", False)
    if not isinstance(overwrite, bool):
        raise ValueError("'overwrite_existing' must be true or false.")

    api_key = config.get("krdict_api_key", "")
    if not isinstance(api_key, str):
        raise ValueError("'krdict_api_key' must be text.")
    api_key = api_key.strip()
    if api_key and not re.fullmatch(r"[0-9A-Fa-f]{32}", api_key):
        raise ValueError(
            "'krdict_api_key' must be blank or a 32-character hexadecimal key."
        )

    forvo_api_key = config.get("forvo_api_key", "")
    if not isinstance(forvo_api_key, str):
        raise ValueError("'forvo_api_key' must be text.")

    return Settings(
        field_mappings=mappings,
        overwrite_existing=overwrite,
        krdict_api_key=api_key,
        forvo_api_key=forvo_api_key.strip(),
    )


def resolve_note(note: Any, mappings: Sequence[FieldMapping]) -> Resolution:
    """Choose the first configured mapping with a non-empty source value."""
    field_names = set(note.keys())
    found_usable_fields = False

    for mapping in mappings:
        if mapping.destination_field not in field_names:
            continue

        available_sources = [
            field_name
            for field_name in mapping.source_fields
            if field_name in field_names
        ]
        if not available_sources:
            continue

        found_usable_fields = True
        for field_name in available_sources:
            query = str(note[field_name]).strip()
            if query:
                return Resolution(
                    target=NoteTarget(
                        query=query,
                        source_field=field_name,
                        destination_field=mapping.destination_field,
                    ),
                    reason=None,
                )

    reason = "empty_source" if found_usable_fields else "no_mapping"
    return Resolution(target=None, reason=reason)


def merge_audio_field(
    existing_value: Any,
    sound_tag: str,
    replace_existing: bool,
) -> str:
    """Append one new sound tag, or explicitly replace the field."""
    existing = str(existing_value).strip()
    if replace_existing or not existing:
        return sound_tag
    if sound_tag in existing:
        return existing
    return "{} {}".format(existing, sound_tag)


def _parse_mapping(raw_mapping: Any, index: int) -> FieldMapping:
    label = "field_mappings[{}]".format(index)
    if not isinstance(raw_mapping, dict):
        raise ValueError("{} must be an object.".format(label))

    source_fields = raw_mapping.get("source_fields")
    destination_field = raw_mapping.get("destination_field")

    if (
        not isinstance(source_fields, list)
        or not source_fields
        or any(
            not isinstance(field, str) or not field.strip()
            for field in source_fields
        )
    ):
        raise ValueError(
            "{}.source_fields must be a non-empty list of field names.".format(label)
        )
    if not isinstance(destination_field, str) or not destination_field.strip():
        raise ValueError("{}.destination_field must be a field name.".format(label))

    normalized_sources = tuple(
        dict.fromkeys(field.strip() for field in source_fields)
    )
    return FieldMapping(
        source_fields=normalized_sources,
        destination_field=destination_field.strip(),
    )
