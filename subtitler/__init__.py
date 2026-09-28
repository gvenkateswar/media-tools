"""Live bilingual (English + Welsh) subtitles.

A small local web app: the browser captures the show's audio (a browser tab
or the microphone), cuts it into short phrases, and sends each one to a
speech model. Welsh speech is translated to English, English speech is
transcribed, so there are always English subtitles on screen.

Run:  python -m subtitler            (then the browser opens the app)
"""
__version__ = "0.1.0"
