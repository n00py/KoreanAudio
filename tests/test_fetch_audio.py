import base64
import json
import unittest
from unittest.mock import patch

from fetch_audio import (
    AudioFile,
    HttpResponse,
    _audio_extension,
    _decode_forvo_audio_url,
    _lookup_text,
    _safe_audio_filename,
    fetch_audio,
    fetch_from_krdict,
    fetch_from_naver,
    fetch_from_forvo_api,
    get_entry_id,
    get_forvo_audio_url,
)


class FetchAudioTests(unittest.TestCase):
    @patch("fetch_audio._http_get")
    def test_krdict_fetches_sound_for_an_exact_headword(self, http_get):
        search_xml = """
            <channel>
              <item>
                <target_code>12345</target_code>
                <word>안녕</word>
              </item>
            </channel>
        """.encode("utf-8")
        view_xml = """
            <channel>
              <item>
                <word_info><word>안녕</word></word_info>
                <multimedia_info>
                  <label>안녕 소리</label>
                  <type>소리</type>
                  <link>https://media.example.test/hello.mp3</link>
                </multimedia_info>
              </item>
            </channel>
        """.encode("utf-8")
        http_get.side_effect = [
            HttpResponse(search_xml, "https://krdict.korean.go.kr/api/search", "text/xml"),
            HttpResponse(view_xml, "https://krdict.korean.go.kr/api/view", "text/xml"),
            HttpResponse(
                b"ID3 official audio",
                "https://media.example.test/hello.mp3",
                "audio/mpeg",
            ),
        ]

        audio = fetch_from_krdict("『안녕?』", "A" * 32)

        self.assertEqual(audio, AudioFile("안녕.mp3", b"ID3 official audio"))
        search_params = http_get.call_args_list[0].kwargs["params"]
        self.assertEqual(search_params["q"], "안녕")
        self.assertEqual(search_params["method"], "exact")
        self.assertEqual(search_params["multimedia"], 5)
        self.assertEqual(
            http_get.call_args_list[1].kwargs["params"]["method"],
            "target_code",
        )

    @patch("fetch_audio._http_get")
    def test_krdict_tries_later_exact_entries_when_first_has_no_audio(
        self,
        http_get,
    ):
        search_xml = """
            <channel>
              <item><target_code>first</target_code><word>수선</word></item>
              <item><target_code>second</target_code><word>수선</word></item>
            </channel>
        """.encode("utf-8")
        no_audio_xml = """
            <channel><item><word_info><word>수선</word></word_info></item></channel>
        """.encode("utf-8")
        audio_xml = """
            <channel>
              <item>
                <word_info><word>수선</word></word_info>
                <multimedia_info>
                  <type>소리</type>
                  <link>https://media.example.test/repair.mp3</link>
                </multimedia_info>
              </item>
            </channel>
        """.encode("utf-8")
        http_get.side_effect = [
            HttpResponse(search_xml, "https://krdict.example/search", "text/xml"),
            HttpResponse(no_audio_xml, "https://krdict.example/view", "text/xml"),
            HttpResponse(audio_xml, "https://krdict.example/view", "text/xml"),
            HttpResponse(
                b"ID3 later official audio",
                "https://media.example.test/repair.mp3",
                "audio/mpeg",
            ),
        ]

        self.assertEqual(
            fetch_from_krdict("수선", "A" * 32),
            AudioFile("수선.mp3", b"ID3 later official audio"),
        )
        self.assertEqual(http_get.call_args_list[1].kwargs["params"]["q"], "first")
        self.assertEqual(http_get.call_args_list[2].kwargs["params"]["q"], "second")

    @patch("fetch_audio._http_get")
    def test_krdict_rejects_nonmatching_search_result(self, http_get):
        http_get.return_value = HttpResponse(
            """
                <channel>
                  <item>
                    <target_code>12345</target_code>
                    <word>학생</word>
                  </item>
                </channel>
            """.encode("utf-8"),
            "https://krdict.korean.go.kr/api/search",
            "text/xml",
        )

        self.assertIsNone(
            fetch_from_krdict("저는 학생입니다.", "B" * 32)
        )
        self.assertEqual(http_get.call_count, 1)

    @patch("fetch_audio._http_get")
    def test_krdict_handles_api_error_xml(self, http_get):
        http_get.return_value = HttpResponse(
            b"<error><error_code>020</error_code><message>Bad key</message></error>",
            "https://krdict.korean.go.kr/api/search",
            "text/xml",
        )

        self.assertIsNone(fetch_from_krdict("안녕", "C" * 32))

    @patch("fetch_audio.fetch_from_forvo")
    @patch("fetch_audio.fetch_from_forvo_api")
    @patch("fetch_audio.fetch_from_naver")
    @patch("fetch_audio.fetch_from_krdict")
    def test_naver_is_used_before_configured_krdict(
        self,
        krdict,
        naver,
        forvo_api,
        forvo,
    ):
        naver_audio = AudioFile("안녕.mp3", b"naver")
        naver.return_value = naver_audio

        self.assertEqual(
            fetch_audio("안녕", "D" * 32, "test-key"),
            naver_audio,
        )
        naver.assert_called_once_with("안녕")
        krdict.assert_not_called()
        forvo_api.assert_not_called()
        forvo.assert_not_called()

    @patch("fetch_audio.fetch_from_forvo")
    @patch("fetch_audio.fetch_from_forvo_api")
    @patch("fetch_audio.fetch_from_naver")
    @patch("fetch_audio.fetch_from_krdict")
    def test_configured_krdict_is_used_after_naver_miss(
        self,
        krdict,
        naver,
        forvo_api,
        forvo,
    ):
        official = AudioFile("안녕.mp3", b"official")
        naver.return_value = None
        krdict.return_value = official

        self.assertEqual(fetch_audio("안녕", "D" * 32), official)
        naver.assert_called_once_with("안녕")
        krdict.assert_called_once_with("안녕", "D" * 32)
        forvo_api.assert_not_called()
        forvo.assert_not_called()

    @patch("fetch_audio.fetch_from_forvo")
    @patch("fetch_audio.fetch_from_forvo_api")
    @patch("fetch_audio.fetch_from_naver")
    @patch("fetch_audio.fetch_from_krdict")
    def test_blank_keys_skip_keyed_providers(
        self,
        krdict,
        naver,
        forvo_api,
        forvo,
    ):
        fallback = AudioFile("안녕.mp3", b"fallback")
        naver.return_value = fallback

        self.assertEqual(fetch_audio("안녕"), fallback)
        krdict.assert_not_called()
        naver.assert_called_once_with("안녕")
        forvo_api.assert_not_called()
        forvo.assert_not_called()

    @patch("fetch_audio.fetch_from_forvo")
    @patch("fetch_audio.fetch_from_forvo_api")
    @patch("fetch_audio.fetch_from_naver")
    def test_forvo_api_is_used_before_public_fallback(
        self,
        naver,
        forvo_api,
        forvo,
    ):
        api_audio = AudioFile("안녕.mp3", b"forvo-api")
        naver.return_value = None
        forvo_api.return_value = api_audio

        self.assertEqual(
            fetch_audio("안녕", forvo_api_key="test-key"),
            api_audio,
        )
        naver.assert_called_once_with("안녕")
        forvo_api.assert_called_once_with("안녕", "test-key")
        forvo.assert_not_called()

    @patch("fetch_audio._http_get")
    def test_forvo_api_downloads_standard_korean_pronunciation(self, http_get):
        payload = {
            "items": [
                {
                    "word": "안녕",
                    "pathmp3": "https://audio.example.test/hello.mp3",
                }
            ]
        }
        http_get.side_effect = [
            HttpResponse(
                json.dumps(payload).encode("utf-8"),
                "https://apifree.forvo.com/",
                "application/json",
            ),
            HttpResponse(
                b"ID3 forvo api",
                "https://audio.example.test/hello.mp3",
                "audio/mpeg",
            ),
        ]

        audio = fetch_from_forvo_api("『안녕?』", "test-key")

        self.assertEqual(audio, AudioFile("안녕.mp3", b"ID3 forvo api"))
        request_url = http_get.call_args_list[0].args[0]
        self.assertIn("/action/standard-pronunciation/", request_url)
        self.assertIn("/language/ko", request_url)

    @patch("fetch_audio._http_get")
    def test_forvo_api_rejects_mismatched_or_error_results(self, http_get):
        mismatched = {
            "items": [
                {
                    "word": "학생",
                    "pathmp3": "https://audio.example.test/student.mp3",
                }
            ]
        }
        http_get.side_effect = [
            HttpResponse(
                json.dumps(mismatched).encode("utf-8"),
                "https://apifree.forvo.com/",
                "application/json",
            ),
            HttpResponse(
                b'["Account disabled."]',
                "https://apifree.forvo.com/",
                "application/json",
            ),
        ]

        self.assertIsNone(fetch_from_forvo_api("안녕", "test-key"))
        self.assertIsNone(fetch_from_forvo_api("안녕", "test-key"))

    def test_decodes_forvo_mp3_before_ogg(self):
        ogg = base64.b64encode(b"aa/example.ogg").decode("ascii")
        mp3 = base64.b64encode(b"bb/example.mp3").decode("ascii")
        onclick = "Play(1,'{}','example.ogg',false,'{}','example.mp3')".format(
            ogg,
            mp3,
        )

        self.assertEqual(
            _decode_forvo_audio_url(onclick),
            "https://audio00.forvo.com/audios/mp3/bb/example.mp3",
        )

    @patch("fetch_audio._http_get")
    def test_extracts_play_call_from_korean_container(self, http_get):
        mp3 = base64.b64encode(b"bb/example.mp3").decode("ascii")
        page = """
            <div id="language-container-ko">
              <span onclick="Play(1,'bad','example.ogg',false,'{}','example.mp3')"></span>
            </div>
            <div id="language-container-en"></div>
        """.format(mp3)
        http_get.return_value = HttpResponse(
            page.encode("utf-8"),
            "https://forvo.com/word/test/",
            "text/html",
        )

        self.assertEqual(
            get_forvo_audio_url("안녕"),
            "https://audio00.forvo.com/audios/mp3/bb/example.mp3",
        )

    def test_lookup_text_removes_surrounding_unicode_punctuation(self):
        self.assertEqual(_lookup_text("  『안녕?』  "), "안녕")
        self.assertEqual(_lookup_text("저는 학생입니다."), "저는 학생입니다")

    @patch("fetch_audio._http_get")
    def test_naver_requires_an_exact_headword_match(self, http_get):
        items = [
            {
                "entryId": "partial",
                "matchType": "term:or",
                "handleEntry": "학생",
            },
            {
                "entryId": "exact",
                "matchType": "exact:entry",
                "handleEntry": "안녕",
            },
        ]
        payload = {
            "searchResultMap": {
                "searchResultListMap": {"WORD": {"items": items}}
            }
        }
        http_get.return_value = HttpResponse(
            json.dumps(payload).encode("utf-8"),
            "https://ko.dict.naver.com/",
            "application/json",
        )

        self.assertEqual(get_entry_id("『안녕?』"), "exact")
        self.assertEqual(http_get.call_args.kwargs["params"]["query"], "안녕")

    @patch("fetch_audio._http_get")
    def test_naver_rejects_partial_sentence_result(self, http_get):
        payload = {
            "searchResultMap": {
                "searchResultListMap": {
                    "WORD": {
                        "items": [
                            {
                                "entryId": "partial",
                                "matchType": "term:or",
                                "handleEntry": "학생",
                            }
                        ]
                    }
                }
            }
        }
        http_get.return_value = HttpResponse(
            json.dumps(payload).encode("utf-8"),
            "https://ko.dict.naver.com/",
            "application/json",
        )

        self.assertIsNone(get_entry_id("저는 학생입니다."))

    @patch("fetch_audio._http_get")
    def test_naver_tries_later_exact_entries_when_first_has_no_audio(
        self,
        http_get,
    ):
        payload = {
            "searchResultMap": {
                "searchResultListMap": {
                    "WORD": {
                        "items": [
                            {
                                "entryId": "first",
                                "matchType": "exact:entry",
                                "handleEntry": "수선",
                            },
                            {
                                "entryId": "second",
                                "matchType": "exact:entry",
                                "handleEntry": "수선",
                            },
                        ]
                    }
                }
            }
        }
        no_audio_entry = {"entry": {"members": [{"prons": []}]}}
        audio_entry = {
            "entry": {
                "members": [
                    {
                        "prons": [
                            {
                                "female_pron_file": (
                                    "https://audio.example.test/repair.mp3"
                                )
                            }
                        ]
                    }
                ]
            }
        }
        http_get.side_effect = [
            HttpResponse(
                json.dumps(payload).encode("utf-8"),
                "https://ko.dict.naver.com/search",
                "application/json",
            ),
            HttpResponse(
                json.dumps(no_audio_entry).encode("utf-8"),
                "https://ko.dict.naver.com/entry/first",
                "application/json",
            ),
            HttpResponse(
                json.dumps(audio_entry).encode("utf-8"),
                "https://ko.dict.naver.com/entry/second",
                "application/json",
            ),
            HttpResponse(
                b"ID3 later Naver audio",
                "https://audio.example.test/repair.mp3",
                "audio/mpeg",
            ),
        ]

        self.assertEqual(
            fetch_from_naver("수선"),
            AudioFile("수선.mp3", b"ID3 later Naver audio"),
        )
        self.assertEqual(http_get.call_args_list[1].kwargs["params"]["entryId"], "first")
        self.assertEqual(http_get.call_args_list[2].kwargs["params"]["entryId"], "second")

    def test_portable_filename_replaces_windows_unsafe_characters(self):
        self.assertEqual(
            _safe_audio_filename('a<b>:"c"/d\\e|f?* .', ".mp3"),
            "a_b___c__d_e_f__.mp3",
        )
        self.assertEqual(_safe_audio_filename("CON", ".mp3"), "_CON.mp3")
        self.assertEqual(_safe_audio_filename("CON.test", ".mp3"), "_CON.test.mp3")

    def test_extension_uses_url_then_content_type(self):
        self.assertEqual(
            _audio_extension("https://example.test/audio/file.ogg", "audio/mpeg"),
            ".ogg",
        )
        self.assertEqual(
            _audio_extension("https://example.test/audio?id=1", "audio/mpeg"),
            ".mp3",
        )


if __name__ == "__main__":
    unittest.main()
