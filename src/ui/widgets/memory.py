"""Widget displaying memory usage."""

import logging
from typing import Any

from textual.widgets import Static

from ...monitor import MemoryInfo

logger = logging.getLogger(__name__)


class MemoryWidget(Static):
    """Widget displaying memory usage."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize memory widget."""
        super().__init__(**kwargs)
        self.memory_info: MemoryInfo | None = None
        logger.info("MemoryWidget initialized")

    def update_memory(self, memory_info: MemoryInfo | None):
        """Update memory data.

        Args:
            memory_info: Updated memory information
        """
        if memory_info:
            logger.info(f"MemoryWidget updated: usage={memory_info.usage_percent:.1f}%, used={memory_info.used_mb/1024:.1f}GB/{memory_info.total_mb/1024:.1f}GB")
        else:
            logger.warning("MemoryWidget updated with no data")
        self.memory_info = memory_info
        self.refresh()

    def render(self) -> str:
        """Render the memory widget."""
        if not self.memory_info:
            return "[dim]No data available[/dim]"

        mem = self.memory_info
        usage = mem.usage_percent
        bar_width = 25
        filled = int((usage / 100.0) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Use consistent blue color
        color = "dodger_blue2"

        used_gb = mem.used_mb / 1024.0
        total_gb = mem.total_mb / 1024.0

        return f"[{color}]{bar}[/{color}] {usage:5.1f}% ({used_gb:.1f}/{total_gb:.1f} GB)"
