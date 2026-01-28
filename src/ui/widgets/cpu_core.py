"""Widget displaying a single CPU core's usage."""

import logging
from typing import Any

from textual.reactive import reactive
from textual.widgets import Static

from ...monitor import CPUCore

logger = logging.getLogger(__name__)


class CPUCoreWidget(Static):
    """Widget displaying a single CPU core's usage."""

    usage_percent = reactive(0.0)

    def __init__(self, core: CPUCore, **kwargs: Any) -> None:
        """Initialize CPU core widget.

        Args:
            core: CPU core data
        """
        super().__init__(**kwargs)
        self.core = core
        self.usage_percent = core.usage_percent
        logger.info(f"CPUCoreWidget initialized: core_id={core.core_id}, usage={core.usage_percent:.1f}%")

    def update_core(self, core: CPUCore):
        """Update core data.

        Args:
            core: Updated CPU core data
        """
        logger.info(f"CPUCoreWidget updated: core_id={core.core_id}, usage={core.usage_percent:.1f}%")
        self.core = core
        self.usage_percent = core.usage_percent
        self.refresh()

    def render(self) -> str:
        """Render the CPU core widget."""
        usage = self.usage_percent
        bar_width = 15
        filled = int((usage / 100.0) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Use consistent blue color
        color = "dodger_blue2"

        return f"  Core {self.core.core_id:2d}: [{color}]{bar}[/{color}] {usage:5.1f}%"
