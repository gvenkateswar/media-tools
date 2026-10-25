# Live Subtitles: English + Welsh

Always-on English subtitles for shows that mix English and Welsh (Cymraeg).
The app listens to the show's audio. English speech is written out as is.
Welsh speech is translated to English, and the Welsh words can be shown
underneath in italics.

```
 [EN] So where were you last night?
 [CY] I was at my mother's house.
      Roeddwn i yn nhŷ Mam.
```

## Two ways to run it

### Option A: free, on your own computer (recommended to try first)

Needs Python 3.9+.

```sh
pip install -r subtitler/requirements.txt
python -m subtitler                 # opens http://localhost:8765 in your browser
```

The first run downloads the speech model (about 500 MB for `small`).

Pick a model size for your computer. Bigger models understand Welsh much
better, but they are slower:

| Model | Welsh quality | Needs |
|-------|---------------|-------|
| `small` (default) | OK for clear speech | Any recent laptop |
| `medium` | Good | Fast CPU, or any NVIDIA GPU |
| `large-v3` | Best | NVIDIA GPU recommended |

```sh
python -m subtitler --model medium
```

If the subtitles fall more than a few seconds behind, use a smaller model or
lower "Max phrase length" in the app.

### Option B: OpenAI Whisper API (best Welsh without a strong computer)

1. Get an API key at <https://platform.openai.com/api-keys>.
2. Open `subtitler/index.html` in Chrome or Edge (double-click it), or use
   the page from Option A.
3. Choose **OpenAI Whisper API** and paste the key. It is saved only in your
   browser.

Cost is about $0.006 per minute of English speech and about double that for
Welsh (one call to write it out, one to translate). A one-hour episode is
roughly $0.40 to $0.70.

## Using it

1. **Audio source**
   - **A browser tab**: for iPlayer, S4C Clic, YouTube and similar. Click
     *Start listening*, pick the tab with the show, and tick
     **Share tab audio**. You keep hearing the show as normal.
   - **Microphone**: for a real TV. Put the laptop or phone near the speaker.
2. Click **Pop out subtitles** to open a small window that stays on top of
   other windows. Drag it under the video. (Chrome and Edge only.)
3. Adjust the subtitle size with the slider.
4. **Download .srt** saves everything so far as a subtitle file.

Keep **Only English and Welsh are spoken** ticked for this kind of show.
Whisper sometimes mistakes short Welsh phrases for Irish or Breton. This
setting forces it to choose between English and Welsh.

## Things to know

- Subtitles appear 2 to 8 seconds after the words are spoken. The app has
  to hear a whole phrase before it can translate it.
- Whisper's Welsh is weaker than its English. Names and fast, overlapping
  speech come out worst. Loud background music also hurts accuracy.
- Tab audio capture needs Chrome or Edge on a desktop computer. Some
  streaming sites with copy protection may block it; use the microphone
  option if the tab gives no sound.
- In local mode nothing leaves your computer. In OpenAI mode, the audio
  clips are sent to OpenAI.

## Files

```
subtitler/
  index.html        # the whole app: audio capture, phrase cutting, display
  server.py         # local Whisper server (python -m subtitler)
  requirements.txt  # faster-whisper, numpy
```
