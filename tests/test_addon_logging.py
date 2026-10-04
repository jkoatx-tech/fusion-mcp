"""The add-in package must not stack log handlers across Stop/Run."""

import importlib.util
import logging
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "addon", "server",
                     "__init__.py")


def _load(name):
    # Load the file directly: importing the add-in package would pull in adsk.
    spec = importlib.util.spec_from_file_location(name, _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reimport_keeps_one_handler_each(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    logger = logging.getLogger("fusion360mcp")
    try:
        _load("addon_run_1")
        _load("addon_run_2")  # what Fusion does on Stop/Run
        assert len(logger.handlers) == 2  # one file, one stdout
    finally:
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()
