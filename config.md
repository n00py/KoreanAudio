# Korean Native Audio settings

Use **Tools → Korean Native Audio Settings…** to configure the add-on with
regular input fields and buttons.

- Add one mapping row for each note-field layout you use.
- Enter multiple input field names with commas between them.
- Choose the field where Anki should save the audio.
- Reorder mappings with **Move up** and **Move down**.
- Existing content is appended to by default; replacement is an explicit choice.
- KRDICT and Forvo API keys are optional and stay in local add-on settings.
- Add an ElevenLabs API key to enable the separate **✨ ElevenLabs** button. It uses
  the clear-slow 0.78× shadowing preset for both words and sentences.

The provider order is Naver, KRDICT when configured, Forvo API when configured,
then the best-effort public Forvo fallback.

ElevenLabs is intentionally separate from that provider chain. It runs only
when you click **✨ ElevenLabs**, choose an ElevenLabs menu action, or choose
**Generate with ElevenLabs** in the no-dictionary-audio dialog.
