"""UEMCP Bridge - local HTTP JSON-RPC bridge for the UE 5.4 editor.

This package must only be imported inside the Unreal Editor Python environment
(or a test harness that stubs ``unreal``).  All ``unreal`` API access is routed
through the game-thread dispatcher.
"""

from .settings import PLUGIN_VERSION, BRIDGE_PROTOCOL

__all__ = ["PLUGIN_VERSION", "BRIDGE_PROTOCOL"]
