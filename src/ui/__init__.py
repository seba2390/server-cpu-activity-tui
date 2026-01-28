"""TUI (Terminal User Interface) package for CPU monitoring.

This package provides a comprehensive Textual-based TUI for monitoring
CPU and memory usage across multiple servers.

Public API:
    - MonitoringApp: Main application class
    - ServerWidget: Widget for displaying server metrics
    - ServerAdded: Message posted when a server is added
    - ServerDeleted: Message posted when a server is deleted
"""

from .app import MonitoringApp
from .messages import ServerAdded, ServerDeleted
from .widgets import ServerWidget

__all__ = [
    "MonitoringApp",
    "ServerWidget",
    "ServerAdded",
    "ServerDeleted",
]
