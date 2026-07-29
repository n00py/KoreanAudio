# Korean Native Audio for Anki

Fetch Korean pronunciation audio into configurable Anki note fields without
locking Anki's interface during network requests.

## Features

- Fetch the current editor/reviewer note from the Tools menu.
- Fetch directly from the note editor with the **🔊 Korean** button or
  **Ctrl+Shift+K**.
- Fetch multiple selected Browser notes from the right-click menu.
- Configure ordered source-field fallbacks and destination fields per note shape.
- Optionally use official Korean Basic Dictionary (KRDICT) and Forvo API audio
  with your own keys.
- Use a predictable provider order: Naver → KRDICT → Forvo API → best-effort
  public Forvo extraction.
- Require an exact dictionary headword match instead of attaching one word from
  a sentence or a verb's basic form.
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

The same window accepts an optional 32-character KRDICT Open API key and an
optional Forvo API key. Keys are stored only in the local Anki add-on settings
and are hidden in the window unless **Show API keys** is checked. The packaged
defaults never contain a key. A regular or Premium Forvo website login is
separate from Forvo API access; the add-on does not store a Forvo username or
password.

## Usage

- Note editor: click **🔊 Korean** or press **Ctrl+Shift+K**
- Current reviewer/editor note: **Tools → Fetch Korean Audio for Current Note**
- Configuration: **Tools → Korean Native Audio Settings…**
- Selected notes: open **Browse**, select notes, then right-click and choose
  **Fetch Korean Audio for Selected Notes**

If all enabled automatic sources miss on a single note, the add-on offers to
open the Korean Forvo page for manual download. Forvo's page markup can change,
so its automatic extractor is intentionally treated as a fallback.

This is a dictionary-audio add-on, not text-to-speech. Surrounding punctuation
such as `?` is ignored for lookup, but full sentences and conjugated forms are
skipped when the source only provides a different headword. The destination is
left unchanged in that case.

Your card template must include the configured destination field, such as
`{{Sound}}`, for the audio to play.

## Development

The provider and field-mapping code are testable without Anki:

```sh
python -m unittest discover -s tests -v
```
