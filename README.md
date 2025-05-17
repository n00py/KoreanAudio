# Korean Audio Fetcher for Anki

This Anki add-on allows you to automatically fetch Korean pronunciation audio for notes that contain a "Korean" field and insert it into a "Sound" field.

## 📦 Features

- ✅ Fetch audio for the **currently edited note** via the Tools menu.
- ✅ Fetch audio for **multiple selected notes** via right-click in the browser.
- ✅ Overwrites the "Sound" field **only if audio is successfully retrieved**.
- ❌ Skips notes with empty Korean fields or when no audio is found.
- 📋 Shows success/failure count after batch fetch.

## 🔧 Requirements

- Note types must have these fields:
  - `Korean` — the word or phrase to look up
  - `Sound` — where the `[sound:...]` tag will be inserted


## 🚀 How to Use

### Fetch for One Note
- Open the **main Anki window**.
- Go to **Tools → Fetch Korean Audio for Current Note**.
  - Only works when you're actively editing a note.

### Fetch for Many Notes
- Open the **Browse window**.
- Select multiple notes.
- Right-click → **Fetch Korean Audio for Selected Notes**.

## 🧠 Notes

- Audio files are downloaded from Naver Dictionary.
- Files are saved to your Anki media folder (e.g. `collection.media/`).
- You must ensure your card template includes `{{Sound}}` where you want the audio to play.

## ✅ Example Card Template

**Back Template**
```html
{{Korean}}<br>
{{Sound}}
```

## 🙋 Support

If the audio doesn't play:
- Make sure `{{Sound}}` is on your card.
- Make sure `[sound:filename.mp3]` is inserted correctly.
- Check that the file exists in `collection.media/`.
