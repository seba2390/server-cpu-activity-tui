"""Custom status bar showing server statistics."""

import logging
from datetime import UTC, datetime

from textual.widgets import Static

logger = logging.getLogger(__name__)


class StatusBar(Static):
    """Custom status bar showing server statistics."""

    def __init__(self, **kwargs):
        """Initialize status bar."""
        super().__init__(**kwargs)
        self.total_servers = 0
        self.connected_servers = 0
        self.average_cpu = 0.0
        self.last_update = ""
        self._status_text = "Initializing..."
        logger.info("StatusBar initialized")

    def update_stats(
        self,
        total: int,
        connected: int,
        average_cpu: float,
        last_update_time: float | None = None
    ):
        """Update status bar statistics.

        Args:
            total: Total number of servers
            connected: Number of connected servers
            average_cpu: Average CPU usage across all servers
            last_update_time: Timestamp of last update
        """
        self.total_servers = total
        self.connected_servers = connected
        self.average_cpu = average_cpu

        if last_update_time:
            dt = datetime.fromtimestamp(last_update_time, tz=UTC)
            self.last_update = dt.strftime("%H:%M:%S")
        else:
            self.last_update = "--:--:--"

        logger.info(f"StatusBar updated: total={total}, connected={connected}, disconnected={total-connected}, avg_cpu={average_cpu:.1f}%, updated={self.last_update}")
        self.refresh_display()

    def refresh_display(self):
        """Refresh the status bar display."""
        disconnected = self.total_servers - self.connected_servers

        # Color code connection status
        if self.connected_servers == self.total_servers:
            conn_color = "green"
        elif self.connected_servers == 0:
            conn_color = "red"
        else:
            conn_color = "yellow"

        # Color code average CPU
        if self.average_cpu < 30:
            cpu_color = "green"
        elif self.average_cpu < 70:
            cpu_color = "yellow"
        else:
            cpu_color = "red"

        self._status_text = (
            f"Servers: [{conn_color}]{self.connected_servers}[/{conn_color}]/{self.total_servers} "
            f"([red]{disconnected}[/red] offline) │ "
            f"Avg CPU: [{cpu_color}]{self.average_cpu:.1f}%[/{cpu_color}] │ "
            f"Updated: [dim]{self.last_update}[/dim]"
        )

        self.update(self._status_text)

    def render(self) -> str:
        """Render the status bar."""
        return self._status_text
