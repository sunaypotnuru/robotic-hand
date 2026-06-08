"""
conftest.py — CI-safe test configuration for LUNA Robotic Arm
=============================================================
Stubs out heavy ML/hardware packages that are not installed in the
GitHub Actions CI environment (torch, ultralytics, mediapipe, whisper,
google-generativeai, PyAudio, pyttsx3, comtypes, serial).

This file is loaded automatically by pytest before any test module is
imported, so the stubs are in sys.modules before `app.py` or any AI
module tries to import them.
"""

import sys
import types
import unittest.mock as mock


def _make_stub(name: str) -> types.ModuleType:
    """Return a minimal ModuleType stub registered under *name*."""
    mod = types.ModuleType(name)
    mod.__spec__ = None  # prevent importlib from complaining
    return mod


# ---------------------------------------------------------------------------
# Packages to stub — add new ones here if CI gains more missing-module errors
# ---------------------------------------------------------------------------

_STUBS = [
    # Deep-learning / vision
    "torch",
    "torch.nn",
    "torch.cuda",
    "torchvision",
    "torchvision.transforms",
    "ultralytics",
    "mediapipe",
    "mediapipe.solutions",
    "mediapipe.solutions.hands",
    "mediapipe.solutions.pose",
    "mediapipe.solutions.drawing_utils",
    "mediapipe.solutions.drawing_styles",
    # Voice / audio
    "speech_recognition",
    "whisper",
    "pyaudio",
    "PyAudio",
    "pyttsx3",
    "comtypes",
    "comtypes.client",
    # Google AI
    "google.generativeai",
    "google",
    "google.generativeai.types",
    # Serial (hardware)
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
]

for _pkg in _STUBS:
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _make_stub(_pkg)

# ---------------------------------------------------------------------------
# Special-case: torch needs a realistic enough surface so that
# `torch.cuda.is_available()` and `torch.device(...)` don't AttributeError.
# ---------------------------------------------------------------------------
_torch = sys.modules["torch"]
_torch.cuda = _make_stub("torch.cuda")
_torch.cuda.is_available = lambda: False
_torch.device = lambda *a, **kw: None
_torch.load = mock.MagicMock(return_value=None)
_torch.no_grad = mock.MagicMock(return_value=mock.MagicMock(
    __enter__=mock.MagicMock(return_value=None),
    __exit__=mock.MagicMock(return_value=False),
))

# ---------------------------------------------------------------------------
# serial needs list_ports.comports() to return an empty list
# ---------------------------------------------------------------------------
_serial = sys.modules["serial"]
_serial.Serial = mock.MagicMock()
_serial.SerialException = Exception
_lp = sys.modules["serial.tools.list_ports"]
_lp.comports = lambda: []

# ---------------------------------------------------------------------------
# speech_recognition needs a usable Recognizer class
# ---------------------------------------------------------------------------
_sr = sys.modules["speech_recognition"]
_sr.Recognizer = mock.MagicMock()
_sr.Microphone = mock.MagicMock()
_sr.AudioData = mock.MagicMock()
_sr.UnknownValueError = Exception
_sr.RequestError = Exception

# ---------------------------------------------------------------------------
# pyttsx3 needs init()
# ---------------------------------------------------------------------------
_pyttsx3 = sys.modules["pyttsx3"]
_pyttsx3.init = mock.MagicMock(return_value=mock.MagicMock())

# ---------------------------------------------------------------------------
# google.generativeai needs configure() and GenerativeModel
# ---------------------------------------------------------------------------
_genai = sys.modules["google.generativeai"]
_genai.configure = mock.MagicMock()
_genai.GenerativeModel = mock.MagicMock()
