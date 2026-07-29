import unittest

from field_mapping import (
    FieldMapping,
    merge_audio_field,
    resolve_note,
    settings_from_config,
)


class FieldMappingTests(unittest.TestCase):
    def test_defaults_preserve_original_field_names(self):
        settings = settings_from_config(None)
        result = resolve_note({"Korean": " 안녕 ", "Sound": ""}, settings.field_mappings)

        self.assertEqual(result.target.query, "안녕")
        self.assertEqual(result.target.source_field, "Korean")
        self.assertEqual(result.target.destination_field, "Sound")
        self.assertFalse(settings.overwrite_existing)
        self.assertEqual(settings.krdict_api_key, "")
        self.assertEqual(settings.forvo_api_key, "")

    def test_uses_first_non_empty_source_and_later_mapping(self):
        mappings = (
            FieldMapping(("Korean", "Expression"), "Sound"),
            FieldMapping(("Hangul",), "Audio"),
        )

        fallback_source = resolve_note(
            {"Korean": "", "Expression": "감사합니다", "Sound": ""},
            mappings,
        )
        later_mapping = resolve_note(
            {"Hangul": "학교", "Audio": ""},
            mappings,
        )

        self.assertEqual(fallback_source.target.query, "감사합니다")
        self.assertEqual(fallback_source.target.source_field, "Expression")
        self.assertEqual(later_mapping.target.destination_field, "Audio")

    def test_distinguishes_empty_sources_from_missing_mapping(self):
        mappings = (FieldMapping(("Korean",), "Sound"),)

        empty = resolve_note({"Korean": " ", "Sound": ""}, mappings)
        missing = resolve_note({"Front": "안녕", "Back": ""}, mappings)

        self.assertEqual(empty.reason, "empty_source")
        self.assertEqual(missing.reason, "no_mapping")

    def test_rejects_invalid_config(self):
        with self.assertRaisesRegex(ValueError, "non-empty list"):
            settings_from_config({"field_mappings": []})
        with self.assertRaisesRegex(ValueError, "true or false"):
            settings_from_config({"overwrite_existing": "yes"})
        with self.assertRaisesRegex(ValueError, "32-character hexadecimal"):
            settings_from_config({"krdict_api_key": "not-a-key"})
        with self.assertRaisesRegex(ValueError, "must be text"):
            settings_from_config({"forvo_api_key": 123})

    def test_accepts_and_trims_krdict_api_key(self):
        settings = settings_from_config({"krdict_api_key": "  " + "A" * 32 + "  "})

        self.assertEqual(settings.krdict_api_key, "A" * 32)

    def test_accepts_and_trims_forvo_api_key(self):
        settings = settings_from_config({"forvo_api_key": "  test-key  "})

        self.assertEqual(settings.forvo_api_key, "test-key")

    def test_appends_audio_without_erasing_existing_content(self):
        self.assertEqual(
            merge_audio_field(
                "[sound:older.mp3]",
                "[sound:new.mp3]",
                replace_existing=False,
            ),
            "[sound:older.mp3] [sound:new.mp3]",
        )
        self.assertEqual(
            merge_audio_field(
                "A note about this word",
                "[sound:new.mp3]",
                replace_existing=False,
            ),
            "A note about this word [sound:new.mp3]",
        )

    def test_does_not_append_the_same_sound_tag_twice(self):
        existing = "[sound:word.mp3]"
        self.assertEqual(
            merge_audio_field(
                existing,
                "[sound:word.mp3]",
                replace_existing=False,
            ),
            existing,
        )

    def test_replacement_remains_an_explicit_option(self):
        self.assertEqual(
            merge_audio_field(
                "[sound:older.mp3]",
                "[sound:new.mp3]",
                replace_existing=True,
            ),
            "[sound:new.mp3]",
        )


if __name__ == "__main__":
    unittest.main()
