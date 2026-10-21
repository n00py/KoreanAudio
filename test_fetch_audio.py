import unittest
from unittest.mock import patch

import fetch_audio


def _constant_bitrate_mp3(frame_count):
    # MPEG-1 Layer III, 128 kbps, 44.1 kHz: 417 bytes and 1152 samples/frame.
    frame = bytes.fromhex("fffb9000") + bytes(413)
    return frame * frame_count


class NaverAudioSafetyTests(unittest.TestCase):
    def test_exact_member_is_required(self):
        payload = {
            "entry": {
                "members": [
                    {
                        "entry_name": "초대되다",
                        "prons": [{"female_pron_file": "https://bad.example/audio.mp3"}],
                    },
                    {
                        "entry_name": "천막",
                        "prons": [{"female_pron_file": "https://good.example/audio.mp3"}],
                    },
                ]
            }
        }
        response = fetch_audio.HttpResponse(
            data=fetch_audio.json.dumps(payload).encode("utf-8"),
            url=fetch_audio.NAVER_ENTRY_URL,
            content_type="application/json",
        )
        with patch.object(fetch_audio, "_http_get", return_value=response):
            self.assertEqual(
                fetch_audio.get_audio_url("entry", expected_word="천막"),
                "https://good.example/audio.mp3",
            )

    def test_implausibly_long_naver_recording_is_rejected(self):
        response = fetch_audio.HttpResponse(
            data=_constant_bitrate_mp3(180),
            url="https://audio.example/cheonmak.mp3",
            content_type="audio/mpeg",
        )
        with patch.object(fetch_audio, "_http_get", return_value=response):
            self.assertIsNone(
                fetch_audio._download_audio(
                    response.url,
                    "천막",
                    {},
                    max_duration_seconds=fetch_audio._max_pronunciation_duration("천막"),
                )
            )

    def test_normal_short_pronunciation_is_accepted(self):
        response = fetch_audio.HttpResponse(
            data=_constant_bitrate_mp3(30),
            url="https://audio.example/annyeong.mp3",
            content_type="audio/mpeg",
        )
        with patch.object(fetch_audio, "_http_get", return_value=response):
            result = fetch_audio._download_audio(
                response.url,
                "안녕",
                {},
                max_duration_seconds=fetch_audio._max_pronunciation_duration("안녕"),
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "안녕.mp3")


if __name__ == "__main__":
    unittest.main()
