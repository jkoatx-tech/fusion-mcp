"""
Fusion360MCP Add-in (v2)

Registers a CustomEvent so all Fusion API calls run on the main thread.
A TCP socket server (daemon thread) accepts JSON commands and dispatches
them through an EventBridge.
"""

import traceback

import adsk.core
import adsk.fusion

# Globals — prevent GC of handler / server references
_app = None
_ui = None
_bridge = None
_server = None
_handler = None
_log = None


def run(context):
    global _app, _ui, _bridge, _server, _handler, _log

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Late imports so the add-in folder is on sys.path
        from .server import LOG_PATH, get_logger
        from .server.command_handler import CommandHandler
        from .server.event_bridge import EventBridge
        from .server.socket_server import Fusion360MCPServer

        _log = get_logger("main")

        _handler = CommandHandler()
        _bridge = EventBridge(_app, _handler)
        _server = Fusion360MCPServer(_bridge, host="localhost", port=9876)
        _server.start()

        _log.info("Fusion360MCP loaded - server on localhost:9876  "
                   "(log: %s)", LOG_PATH)

    except Exception:
        msg = traceback.format_exc()
        if _ui:
            _ui.messageBox(f"Fusion360MCP failed to start:\n{msg}")
        print(f"Fusion360MCP startup error:\n{msg}")


def stop(context):
    global _app, _ui, _bridge, _server, _handler, _log

    try:
        if _server:
            _server.stop()
        if _bridge:
            _bridge.stop()
    except Exception:
        traceback.print_exc()

    if _log:
        _log.info("Fusion360MCP stopped")

    _server = None
    _bridge = None
    _handler = None
