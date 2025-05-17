import requests
import os
import time
from requests.exceptions import RequestException

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Gecko/20100101 Firefox/106.0",
    "Referer": "https://ko.dict.naver.com/",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

SEARCH_URL = "https://ko.dict.naver.com/api3/koko/search"
ENTRY_URL = "https://ko.dict.naver.com/api/platform/koko/entry"

def get_entry_id(word):
    try:
        resp = requests.get(SEARCH_URL, params={"query": word, "lang": "ko"}, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("searchResultMap", {}).get("searchResultListMap", {}).get("WORD", {}).get("items", [])
        return items[0]["entryId"] if items else None
    except Exception as e:
        print(f"[!] Entry ID fetch error: {e}")
        return None

def get_audio_url(entry_id):
    try:
        params = {"entryId": entry_id, "timestamp": str(int(time.time() * 1000))}
        resp = requests.get(ENTRY_URL, params=params, headers=HEADERS)
        resp.raise_for_status()
        entry = resp.json().get("entry", {})
        members = entry.get("members", [{}])
        prons = members[0].get("prons", [])
        for pron in prons:
            for label in ("female_pron_file", "male_pron_file"):
                if pron.get(label):
                    return pron.get(label)
    except Exception as e:
        print(f"[!] Audio URL fetch error: {e}")
    return None

def fetch_and_save_audio(word):
    from aqt import mw
    AUDIO_DIR = mw.col.media.dir()
    os.makedirs(AUDIO_DIR, exist_ok=True)

    entry_id = get_entry_id(word)
    if not entry_id:
        return None
    url = get_audio_url(entry_id)
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            filename = f"{word}.mp3"
            filepath = os.path.join(AUDIO_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
    except RequestException as e:
        print(f"[!] Audio download error: {e}")
    return None
