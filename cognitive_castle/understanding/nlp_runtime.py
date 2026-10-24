"""One optional, lazy NLP pipeline per process; importing this module is cheap.

Missing installations are cached. An operator may explicitly call ``reset_nlp``
after installing a model; this module never downloads or installs anything.
"""

from threading import Lock

_lock = Lock()
_loaded = False
_nlp = None


def get_nlp():
    """Return the shared optional English pipeline, or None when unavailable."""
    global _loaded, _nlp
    with _lock:
        if not _loaded:
            try:
                import spacy

                _nlp = spacy.load("en_core_web_sm")
            except (ImportError, OSError):
                _nlp = None
            _loaded = True
        return _nlp


def reset_nlp():
    """Explicitly allow the next opt-in call to retry loading the model."""
    global _loaded, _nlp
    with _lock:
        _nlp = None
        _loaded = False
