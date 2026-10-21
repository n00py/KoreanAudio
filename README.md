# Korean Native Audio for Anki

Fetch Korean pronunciation audio into configurable Anki note fields without
locking Anki's interface during network requests.

## Features

- Fetch the current editor/reviewer note from the Tools menu.
- Fetch directly from the note editor with the **🔊 Korean** button or
  **Ctrl+Shift+K**.
- Generate Korean TTS directly from the note editor with the **✨ ElevenLabs** button
  or **Ctrl+Shift+E**. This uses ElevenLabs Anna Kim with the tested clear-slow
  0.78× shadowing preset.
- Fetch multiple selected Browser notes from the right-click menu.
- Configure ordered source-field fallbacks and destination fields per note shape.
- Optionally use official Korean Basic Dictionary (KRDICT) and Forvo API audio
  with your own keys.
- Use a predictable provider order: Naver → KRDICT → Forvo API → best-effort
  public Forvo extraction.
- Require an exact dictionary headword match instead of attaching one word from
  a sentence or a verb's basic form.
- Reject implausibly long Naver pronunciation files, which prevents a mislabeled
  upstream recording from being attached when its duration cannot fit the word.
- Only change a destination field after audio has been downloaded successfully.
- Run network work in the background and report specific batch skip reasons.

## Compatibility

- Anki 2.1.50 or newer
- Windows, macOS, or Linux
- Both Qt 5 and Qt 6 Anki builds

The add-on uses Python's standard library and Anki's bundled APIs; it has no
separately installed Python dependencies.

## Configuration

The default mapping reads `Korean` and writes a `[sound:...]` tag to `Sound`.
Open **Tools → Korean Native Audio Settings…** to use the native settings
window. **Tools → Add-ons → Korean Native Audio → Config** opens the same
window; neither route requires editing JSON.

Each mapping row contains:

- **Read Korean from:** one or more note field names, separated by commas. The
  first non-empty field is used.
- **Save audio to:** the note field that will receive the `[sound:...]` tag.

Rows are tried from top to bottom. Add, remove, or reorder rows to support
different note types. New audio is appended when the destination already has
content, so existing audio or notes are preserved. The same sound tag will not
be added twice. Choose **Replace existing content** only when replacement is
intentional.

The same window accepts an optional 32-character KRDICT Open API key, an
optional Forvo API key, and an ElevenLabs API key. The ElevenLabs key is needed
only for the dedicated Anna button. Keys are stored only in the local Anki
add-on settings and are hidden in the window unless **Show API keys** is
checked. The packaged defaults never contain a key. A regular or Premium Forvo
website login is separate from Forvo API access; the add-on does not store a
Forvo username or password.

## Usage

- Note editor: click **🔊 Korean** or press **Ctrl+Shift+K**
- ElevenLabs: click **✨ ElevenLabs** or press **Ctrl+Shift+E**
- Current reviewer/editor note: **Tools → Fetch Korean Audio for Current Note**
- Current reviewer/editor note with Anna: **Tools → Generate ElevenLabs Korean
  Audio for Current Note**
- Configuration: **Tools → Korean Native Audio Settings…**
- Selected notes: open **Browse**, select notes, then right-click and choose the
  dictionary-fetch or ElevenLabs-generation action.

If all enabled automatic sources miss on a single note, the add-on offers to
either generate Anna audio with ElevenLabs or open the Korean Forvo page for
manual download. Forvo's page markup can change, so its automatic extractor is
intentionally treated as a fallback.

The regular **🔊 Korean** action is dictionary audio: surrounding punctuation
such as `?` is ignored for lookup, but full sentences and conjugated forms are
skipped when the source only provides a different headword. The dedicated
**✨ ElevenLabs** action is text-to-speech and accepts both words and complete
sentences. It uses `eleven_multilingual_v2`, Anna Kim voice ID
`uyVNoMrnUku1dZyVEXwD`, speed `0.78`, stability `0.90`, similarity `0.90`, and
light pauses at long clause boundaries.

Your card template must include the configured destination field, such as
`{{Sound}}`, for the audio to play.
