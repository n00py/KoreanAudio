"""Network providers for Korean pronunciation audio.

This module intentionally has no Anki or Qt imports, so network work can run
on Anki's background thread and the provider logic can be tested on its own.
"""

import base64
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ElementTree
from html import unescape
from typing import NamedTuple, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


KRDICT_SEARCH_URL = "https://krdict.korean.go.kr/api/search"
KRDICT_VIEW_URL = "https://krdict.korean.go.kr/api/view"
NAVER_SEARCH_URL = "https://ko.dict.naver.com/api3/koko/search"
NAVER_ENTRY_URL = "https://ko.dict.naver.com/api/platform/koko/entry"
FORVO_API_BASE_URL = "https://apifree.forvo.com"
FORVO_WORD_URL = "https://forvo.com/word/"
ELEVENLABS_TTS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_ANNA_VOICE_ID = "uyVNoMrnUku1dZyVEXwD"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.90,
    "similarity_boost": 0.90,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 0.78,
}

KRDICT_HEADERS = {
    "User-Agent": "KoreanNativeAudio/0.6.0",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://krdict.korean.go.kr/",
}
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 KoreanNativeAudio/0.6.0",
    "Referer": "https://ko.dict.naver.com/",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}
FORVO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://forvo.com/",
}
FORVO_API_HEADERS = {
    "User-Agent": "KoreanNativeAudio/0.6.0",
    "Accept": "application/json",
    "Referer": "https://api.forvo.com/",
}

ELEVENLABS_NUMBER_READINGS = (
    (r"50분", "오십 분"),
    (r"10분", "십 분"),
    (r"5분", "오 분"),
    (r"4만", "사만"),
    (r"30대", "삼십 대"),
    (r"2미터", "이 미터"),
    (r"8돈", "팔 돈"),
    (r"1년에", "일 년에"),
    (r"1학년", "일 학년"),
    (r"2년", "이 년"),
    (r"6개월", "육 개월"),
    (r"3분", "삼 분"),
)


class HttpResponse(NamedTuple):
    data: bytes
    url: str
    content_type: str


class AudioFile(NamedTuple):
    filename: str
    data: bytes


def fetch_audio(
    word: str,
    krdict_api_key: str = "",
    forvo_api_key: str = "",
) -> Optional[AudioFile]:
    """Try each small provider in order and return the first audio result."""
    word = _lookup_text(word)
    if not word:
        return None

    audio = fetch_from_naver(word)
    if audio:
        return audio

    if krdict_api_key:
        audio = fetch_from_krdict(word, krdict_api_key)
        if audio:
            return audio

    if forvo_api_key:
        audio = fetch_from_forvo_api(word, forvo_api_key)
        if audio:
            return audio

    return fetch_from_forvo(word)


def fetch_from_elevenlabs(text: str, api_key: str) -> Optional[AudioFile]:
    """Generate Anna Kim Korean speech with the shadowing-friendly preset."""
    spoken = elevenlabs_spoken_text(text)
    if not spoken or not api_key.strip():
        return None

    request_text = _add_light_chunking(spoken)
    url = "{}/{}?{}".format(
        ELEVENLABS_TTS_BASE_URL,
        ELEVENLABS_ANNA_VOICE_ID,
        urlencode({"output_format": "mp3_44100_128"}),
    )
    payload = {
        "text": request_text,
        "model_id": ELEVENLABS_MODEL_ID,
        "voice_settings": ELEVENLABS_VOICE_SETTINGS,
    }
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "User-Agent": "KoreanNativeAudio/0.6.0",
        "xi-api-key": api_key.strip(),
    }
    try:
        response = _http_post_json(
            url,
            payload=payload,
            headers=headers,
            timeout=180,
        )
    except (HTTPError, URLError, OSError, ValueError, TypeError):
        return None

    if (
        len(response.data) < 1000
        or response.content_type.startswith("text/")
        or response.content_type in ("application/json", "application/xml")
    ):
        return None
    return AudioFile(
        filename=elevenlabs_audio_filename(text),
        data=response.data,
    )


def elevenlabs_spoken_text(text: str) -> str:
    """Turn an Anki field into clean Korean text suitable for synthesis."""
    value = str(text)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = unicodedata.normalize("NFC", unescape(value)).replace("\xa0", " ")
    # A field such as 그림(을) 그리다 should be spoken as 그림을 그리다.
    value = re.sub(r"\(([^()]*)\)", r"\1", value)
    value = re.sub(r"\s+", " ", value).strip()
    for pattern, replacement in ELEVENLABS_NUMBER_READINGS:
        value = re.sub(pattern, replacement, value)
    return value


def elevenlabs_audio_filename(text: str) -> str:
    """Return the deterministic filename used to avoid repeat paid requests."""
    spoken = elevenlabs_spoken_text(text)
    fingerprint = hashlib.sha1(
        (
            spoken
            + "|"
            + ELEVENLABS_ANNA_VOICE_ID
            + "|"
            + ELEVENLABS_MODEL_ID
            + "|"
            + json.dumps(ELEVENLABS_VOICE_SETTINGS, sort_keys=True)
        ).encode("utf-8")
    ).hexdigest()[:12]
    safe_name = _safe_audio_filename(spoken, ".mp3")[:-4]
    safe_name = safe_name[:72].rstrip(" ._") or "korean"
    return "elevenlabs_anna_{}_{}.mp3".format(safe_name, fingerprint)


def _add_light_chunking(spoken: str) -> str:
    request_text = re.sub(r",\s*", ', <break time="0.28s" /> ', spoken)
    if "<break " in request_text or len(spoken.replace(" ", "")) < 34:
        return request_text
    boundaries = (
        "말하면서도 ",
        "원하는데도 ",
        "있으니까 ",
        "없으니까 ",
        "있지만 ",
        "살아남았지만 ",
        "잘하면 ",
        "똑똑하면 ",
        "때문에 ",
        "없어서 ",
        "편인데 ",
        "마친 다음에 ",
        "들어가면 ",
    )
    for boundary in boundaries:
        if boundary in request_text:
            return request_text.replace(
                boundary,
                boundary + '<break time="0.26s" /> ',
                1,
            )
    return request_text


def fetch_from_krdict(word: str, api_key: str) -> Optional[AudioFile]:
    """Fetch official Korean Basic Dictionary audio for an exact headword."""
    word = _lookup_text(word)
    if not word or not api_key:
        return None

    for target_code in get_krdict_target_codes(word, api_key):
        audio_url = get_krdict_audio_url(target_code, word, api_key)
        if audio_url:
            audio = _download_audio(audio_url, word, KRDICT_HEADERS)
            if audio:
                return audio
    return None


def fetch_from_naver(word: str) -> Optional[AudioFile]:
    for entry_id in get_entry_ids(word):
        audio_url = get_audio_url(entry_id, expected_word=word)
        if audio_url:
            audio = _download_audio(
                audio_url,
                word,
                NAVER_HEADERS,
                max_duration_seconds=_max_pronunciation_duration(word),
            )
            if audio:
                return audio
    return None


def fetch_from_forvo(word: str) -> Optional[AudioFile]:
    audio_url = get_forvo_audio_url(word)
    if not audio_url:
        return None

    return _download_audio(audio_url, word, FORVO_HEADERS)


def fetch_from_forvo_api(word: str, api_key: str) -> Optional[AudioFile]:
    """Fetch Forvo's standard Korean pronunciation with a user API key."""
    word = _lookup_text(word)
    if not word or not api_key:
        return None

    audio_url = get_forvo_api_audio_url(word, api_key)
    if not audio_url:
        return None

    return _download_audio(audio_url, word, FORVO_API_HEADERS)


def get_forvo_api_audio_url(word: str, api_key: str) -> Optional[str]:
    word = _lookup_text(word)
    if not word or not api_key:
        return None

    request_url = (
        FORVO_API_BASE_URL
        + "/key/{}/format/json/action/standard-pronunciation/word/{}/language/ko"
    ).format(
        quote(api_key.strip(), safe=""),
        quote(word, safe=""),
    )

    try:
        response = _http_get(
            request_url,
            headers=FORVO_API_HEADERS,
            timeout=15,
        )
        payload = json.loads(response.data.decode("utf-8"))
        if not isinstance(payload, dict):
            return None

        items = payload.get("items") or []
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return None

        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = item.get("word")
            if candidate and _lookup_text(candidate) != word:
                continue
            for field_name in ("pathmp3", "pathogg"):
                audio_url = item.get(field_name)
                if (
                    isinstance(audio_url, str)
                    and urlparse(audio_url).scheme in ("http", "https")
                ):
                    return audio_url
    except (
        HTTPError,
        URLError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        pass
    return None


def get_krdict_target_code(word: str, api_key: str) -> Optional[str]:
    """Return the first exact target code for compatibility with older callers."""
    target_codes = get_krdict_target_codes(word, api_key)
    return target_codes[0] if target_codes else None


def get_krdict_target_codes(word: str, api_key: str) -> tuple:
    word = _lookup_text(word)
    if not word or not api_key:
        return ()

    try:
        response = _http_get(
            KRDICT_SEARCH_URL,
            headers=KRDICT_HEADERS,
            params={
                "key": api_key,
                "q": word,
                "part": "word",
                "method": "exact",
                "num": 10,
                "multimedia": 5,
            },
            timeout=15,
        )
        root = ElementTree.fromstring(response.data)
        if root.tag == "error":
            return ()

        target_codes = []
        for item in root.findall(".//item"):
            candidate = _lookup_text(item.findtext("word") or "")
            target_code = (item.findtext("target_code") or "").strip()
            if candidate == word and target_code:
                target_codes.append(target_code)
        return tuple(dict.fromkeys(target_codes))
    except (
        ElementTree.ParseError,
        HTTPError,
        URLError,
        OSError,
        ValueError,
        TypeError,
    ):
        pass
    return ()


def get_krdict_audio_url(
    target_code: str,
    word: str,
    api_key: str,
) -> Optional[str]:
    if not target_code or not api_key:
        return None

    try:
        response = _http_get(
            KRDICT_VIEW_URL,
            headers=KRDICT_HEADERS,
            params={
                "key": api_key,
                "method": "target_code",
                "q": target_code,
            },
            timeout=15,
        )
        root = ElementTree.fromstring(response.data)
        if root.tag == "error":
            return None

        entry_word = root.findtext(".//word_info/word")
        if _lookup_text(entry_word or "") != _lookup_text(word):
            return None

        for multimedia in root.findall(".//multimedia_info"):
            media_type = (multimedia.findtext("type") or "").strip().lower()
            link = (multimedia.findtext("link") or "").strip()
            if link and (
                media_type in {"소리", "sound", "audio"}
                or _looks_like_audio_url(link)
            ):
                return link
    except (
        ElementTree.ParseError,
        HTTPError,
        URLError,
        OSError,
        ValueError,
        TypeError,
    ):
        pass
    return None


def get_entry_id(word: str) -> Optional[str]:
    """Return the first exact Naver entry ID for compatibility."""
    entry_ids = get_entry_ids(word)
    return entry_ids[0] if entry_ids else None


def get_entry_ids(word: str) -> tuple:
    word = _lookup_text(word)
    if not word:
        return ()
    try:
        response = _http_get(
            NAVER_SEARCH_URL,
            headers=NAVER_HEADERS,
            params={"query": word, "lang": "ko"},
            timeout=15,
        )
        data = json.loads(response.data.decode("utf-8"))
        items = (
            data.get("searchResultMap", {})
            .get("searchResultListMap", {})
            .get("WORD", {})
            .get("items", [])
        )
        entry_ids = []
        for item in items:
            entry = item.get("handleEntry") or re.sub(
                r"<[^>]+>",
                "",
                str(item.get("expEntry", "")),
            )
            if (
                item.get("matchType") == "exact:entry"
                and _lookup_text(entry) == word
                and item.get("entryId")
            ):
                entry_ids.append(str(item["entryId"]))
        return tuple(dict.fromkeys(entry_ids))
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
        pass
    return ()


def get_audio_url(
    entry_id: str,
    expected_word: Optional[str] = None,
) -> Optional[str]:
    expected_word = _lookup_text(expected_word or "")
    try:
        response = _http_get(
            NAVER_ENTRY_URL,
            headers=NAVER_HEADERS,
            params={"entryId": entry_id},
            timeout=15,
        )
        entry = json.loads(response.data.decode("utf-8")).get("entry", {})
        members = entry.get("members") or []
        for member in members:
            member_word = member.get("entry_name") or member.get("show_full_name")
            if expected_word and _lookup_text(member_word or "") != expected_word:
                continue
            for pronunciation in member.get("prons") or []:
                for field_name in ("female_pron_file", "male_pron_file"):
                    audio_url = pronunciation.get(field_name)
                    if audio_url:
                        return str(audio_url)
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
        pass
    return None


def get_forvo_audio_url(word: str, language: str = "ko") -> Optional[str]:
    try:
        response = _http_get(
            FORVO_WORD_URL + quote(word, safe="") + "/",
            headers=FORVO_HEADERS,
            timeout=15,
        )
        page = response.data.decode("utf-8", errors="replace")
    except (HTTPError, URLError, OSError, ValueError):
        return None

    if "Performing security verification" in page or "Just a moment..." in page:
        return None

    language_container = re.search(
        r'id=["\']language-container-{}["\'].*?'
        r'(?=id=["\']language-container-[\w-]+["\']|$)'.format(
            re.escape(language)
        ),
        page,
        re.DOTALL,
    )
    if not language_container:
        return None

    for match in re.finditer(
        r'onclick\s*=\s*(["\'])(.*?)\1',
        language_container.group(0),
        re.DOTALL,
    ):
        onclick_value = unescape(match.group(2))
        if "Play(" not in onclick_value:
            continue
        audio_url = _decode_forvo_audio_url(onclick_value)
        if audio_url:
            return audio_url

    return None


def _decode_forvo_audio_url(onclick_value: str) -> Optional[str]:
    """Decode the base64 media paths embedded in Forvo's Play(...) call."""
    play_call = re.search(r"Play\((.*?)\)", onclick_value, re.DOTALL)
    if not play_call:
        return None

    decoded_paths = []
    for single_quoted, double_quoted in re.findall(
        r"'([^']*)'|\"([^\"]*)\"",
        play_call.group(1),
    ):
        encoded_value = single_quoted or double_quoted
        try:
            padded = encoded_value + ("=" * (-len(encoded_value) % 4))
            decoded = base64.b64decode(padded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.lower().endswith((".mp3", ".ogg")):
            decoded_paths.append(decoded)

    for extension, base_url in (
        (".mp3", "https://audio00.forvo.com/audios/mp3/"),
        (".ogg", "https://audio00.forvo.com/ogg/"),
    ):
        for path in decoded_paths:
            if path.lower().endswith(extension):
                return base_url + path.lstrip("/")
    return None


def _download_audio(
    url: str,
    word: str,
    headers: dict,
    max_duration_seconds: Optional[float] = None,
) -> Optional[AudioFile]:
    try:
        response = _http_get(url, headers=headers, timeout=20)
    except (HTTPError, URLError, OSError, ValueError):
        return None

    if (
        not response.data
        or response.content_type.startswith("text/")
        or response.content_type in ("application/json", "application/xml")
    ):
        return None

    extension = _audio_extension(response.url, response.content_type)
    if max_duration_seconds is not None and extension == ".mp3":
        duration = _mp3_duration_seconds(response.data)
        if duration is not None and duration > max_duration_seconds:
            return None
    filename = _safe_audio_filename(word, extension)
    return AudioFile(filename=filename, data=response.data)


def _max_pronunciation_duration(word: str) -> float:
    """Allow natural pacing while rejecting obviously unrelated recordings."""
    syllables = sum("\uac00" <= character <= "\ud7a3" for character in word)
    units = syllables or sum(character.isalnum() for character in word)
    return max(2.5, 1.2 + (0.65 * max(units, 1)))


def _mp3_duration_seconds(data: bytes) -> Optional[float]:
    """Return an MP3 duration by walking frames, without external packages."""
    if len(data) < 4:
        return None

    position = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        tag_size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        position = 10 + tag_size
        if data[5] & 0x10:
            position += 10

    bitrate_tables = {
        (3, 1): (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448),
        (3, 2): (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384),
        (3, 3): (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
        (2, 1): (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256),
        (2, 2): (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
        (2, 3): (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
    }
    sample_rates = {
        3: (44100, 48000, 32000),
        2: (22050, 24000, 16000),
        0: (11025, 12000, 8000),
    }

    duration = 0.0
    frames = 0
    while position + 4 <= len(data):
        header = int.from_bytes(data[position : position + 4], "big")
        if (header & 0xFFE00000) != 0xFFE00000:
            position += 1
            continue

        version_id = (header >> 19) & 0x3
        layer_bits = (header >> 17) & 0x3
        bitrate_index = (header >> 12) & 0xF
        sample_rate_index = (header >> 10) & 0x3
        padding = (header >> 9) & 0x1
        if (
            version_id == 1
            or layer_bits == 0
            or bitrate_index in (0, 15)
            or sample_rate_index == 3
        ):
            position += 1
            continue

        layer = 4 - layer_bits
        table_version = 3 if version_id == 3 else 2
        bitrate = bitrate_tables[(table_version, layer)][bitrate_index] * 1000
        sample_rate = sample_rates[version_id][sample_rate_index]
        if layer == 1:
            frame_length = ((12 * bitrate) // sample_rate + padding) * 4
            samples_per_frame = 384
        elif layer == 3 and version_id != 3:
            frame_length = (72 * bitrate) // sample_rate + padding
            samples_per_frame = 576
        else:
            frame_length = (144 * bitrate) // sample_rate + padding
            samples_per_frame = 1152

        if frame_length <= 4 or position + frame_length > len(data):
            break
        duration += samples_per_frame / sample_rate
        frames += 1
        position += frame_length

    return duration if frames >= 2 else None


def _http_get(
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> HttpResponse:
    if params:
        separator = "&" if "?" in url else "?"
        url = url + separator + urlencode(params)

    request = Request(url, headers=headers or {}, method="GET")
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        return HttpResponse(
            data=response.read(),
            url=response.geturl(),
            content_type=content_type,
        )


def _http_post_json(
    url: str,
    payload: dict,
    headers: Optional[dict] = None,
    timeout: int = 180,
) -> HttpResponse:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers or {},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        return HttpResponse(
            data=response.read(),
            url=response.geturl(),
            content_type=content_type,
        )


def _lookup_text(text: str) -> str:
    """Trim whitespace and surrounding punctuation without changing Korean."""
    text = unicodedata.normalize("NFC", unescape(str(text))).strip()
    while text and unicodedata.category(text[0]).startswith("P"):
        text = text[1:].lstrip()
    while text and unicodedata.category(text[-1]).startswith("P"):
        text = text[:-1].rstrip()
    return text


def _audio_extension(url: str, content_type: str) -> str:
    basename = urlparse(url).path.rsplit("/", 1)[-1].lower()
    if basename.endswith((".ogg", ".oga")):
        return ".ogg"
    return ".ogg" if content_type == "audio/ogg" else ".mp3"


def _looks_like_audio_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".mp3", ".ogg", ".oga", ".wav", ".m4a"))


def _safe_audio_filename(word: str, extension: str) -> str:
    """Produce a portable desired name; Anki handles collisions and final storage."""
    stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", word).strip(" .")
    stem = stem[:120].rstrip(" .") or "korean-audio"

    reserved_windows_names = {"CON", "PRN", "AUX", "NUL"}
    reserved_windows_names.update("COM{}".format(number) for number in range(1, 10))
    reserved_windows_names.update("LPT{}".format(number) for number in range(1, 10))
    if stem.split(".", 1)[0].upper() in reserved_windows_names:
        stem = "_" + stem

    if not extension.startswith("."):
        extension = "." + extension
    return stem + extension.lower()
