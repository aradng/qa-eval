"""Helpers for running a test under a flag configuration.

Most of the service reads its config when it needs it, so clearing the cached
config is enough. `app.schemas` is the exception: it builds the served JSON
Schema once, at import time, so changing a flag it depends on means reloading
it and anything holding a reference to it.
"""

import importlib
import os
from contextlib import contextmanager

from app.config import get_config

# Modules holding something computed at import time from a flag.
_RELOAD = ("app.schemas", "app.api")


def _reload() -> None:
    get_config.cache_clear()
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


@contextmanager
def flags(**overrides: bool):
    """Run a block with the given flags set, then restore.

    >>> with flags(DEMO_HEALTH_BUG=True):
    ...     ...
    """
    previous = {k: os.environ.get(k) for k in overrides}
    os.environ.update({k: str(v).lower() for k, v in overrides.items()})
    _reload()
    try:
        yield get_config()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reload()


def armed(name: str) -> bool:
    """True when the named flag is on in the ambient environment.

    Use this to mark a test `xfail(strict=True)` for the configuration the
    fault is armed in — see tests/test_demo_flag.py.
    """
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}
