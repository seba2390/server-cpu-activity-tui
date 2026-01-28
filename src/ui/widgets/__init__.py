"""Widget __init__ for easy imports."""

from .cpu_core import CPUCoreWidget
from .history_plot import HistoryPlotWidget
from .memory import MemoryWidget
from .server import ServerWidget
from .status_bar import StatusBar

__all__ = [
    "CPUCoreWidget",
    "HistoryPlotWidget",
    "MemoryWidget",
    "ServerWidget",
    "StatusBar",
]
