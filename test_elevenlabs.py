import unittest
from unittest.mock import patch

import fetch_audio
from field_mapping import settings_from_config


class ElevenLabsSettingsTests(unittest.TestCase):
    def test_old_config_without_elevenlabs_key_still_loads(self):
        settings = settings_from_config(
            {
                "field_mappings": [
                    {
                        "source_fields": ["Korean"],
                        "destination_field": "Sound",
                    }
                ],
                "overwrite_existing": False,
                "krdict_api_key": "",
                "forvo_api_key": "",
            }
        )
        self.assertEqual(settings.elevenlabs_api_key, "")

    def test_elevenlabs_key_is_trimmed(self):
        settings = settings_from_config({"elevenlabs_api_key": "  secret  "})
        self.assertEqual(settings.elevenlabs_api_key, "secret")

    def test_non_text_elevenlabs_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "elevenlabs_api_key"):
            settings_from_config({"elevenlabs_api_key": 123})


class ElevenLabsTextTests(unittest.TestCase):
    def test_html_optional_particle_and_number_are_normalized(self):
        self.assertEqual(
            fetch_audio.elevenlabs_spoken_text(
                "<div>그림(을) 그리고&nbsp;5분 기다려요.</div>"
            ),
            "그림을 그리고 오 분 기다려요.",
        )

    def test_long_clause_gets_light_pause(self):
        spoken = (
            "아이들에게 두 가지 언어를 배우라고 말하면서도 "
            "저는 한 가지 언어밖에 할 수 없어서 미안했어요."
        )
        request_text = fetch_audio._add_light_chunking(spoken)
        self.assertIn('말하면서도 <break time="0.26s" />', request_text)

    def test_comma_gets_short_pause(self):
        request_text = fetch_audio._add_light_chunking(
            "군대에서는 기회를 얻을 수 있지만, 모두가 활용하지는 않아요."
        )
        self.assertIn(', <break time="0.28s" />', request_text)

    def test_filename_is_stable_and_voice_specific(self):
        first = fetch_audio.elevenlabs_audio_filename("안녕하세요.")
        second = fetch_audio.elevenlabs_audio_filename("안녕하세요.")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("elevenlabs_anna_"))
        self.assertTrue(first.endswith(".mp3"))


class ElevenLabsRequestTests(unittest.TestCase):
    def test_blank_key_never_calls_network(self):
        with patch.object(fetch_audio, "_http_post_json") as post:
            self.assertIsNone(
                fetch_audio.fetch_from_elevenlabs("안녕하세요.", "  ")
            )
        post.assert_not_called()

    def test_request_uses_anna_clear_slow_preset(self):
        response = fetch_audio.HttpResponse(
            data=b"ID3" + bytes(1500),
            url="https://api.elevenlabs.io/audio.mp3",
            content_type="audio/mpeg",
        )
        with patch.object(
            fetch_audio,
            "_http_post_json",
            return_value=response,
        ) as post:
            result = fetch_audio.fetch_from_elevenlabs(
                "안녕하세요.",
                "test-key",
            )

        self.assertIsNotNone(result)
        self.assertGreater(len(result.data), 1000)
        args, kwargs = post.call_args
        self.assertIn(fetch_audio.ELEVENLABS_ANNA_VOICE_ID, args[0])
        self.assertEqual(kwargs["headers"]["xi-api-key"], "test-key")
        self.assertEqual(kwargs["payload"]["model_id"], "eleven_multilingual_v2")
        self.assertEqual(
            kwargs["payload"]["voice_settings"],
            {
                "stability": 0.90,
                "similarity_boost": 0.90,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 0.78,
            },
        )

    def test_json_or_tiny_response_is_rejected(self):
        response = fetch_audio.HttpResponse(
            data=b'{"detail":"quota exceeded"}',
            url="https://api.elevenlabs.io/error",
            content_type="application/json",
        )
        with patch.object(
            fetch_audio,
            "_http_post_json",
            return_value=response,
        ):
            self.assertIsNone(
                fetch_audio.fetch_from_elevenlabs("안녕하세요.", "test-key")
            )


if __name__ == "__main__":
    unittest.main()
