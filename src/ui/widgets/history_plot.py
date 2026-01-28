"""Widget displaying CPU usage history as a custom bar chart."""

import logging

from textual.widgets import Static

logger = logging.getLogger(__name__)


class HistoryPlotWidget(Static):
    """Widget displaying CPU usage history as a vertical bar chart.

    Renders bars using block characters with axis lines.
    New data appears on the left, old data on the right.
    """

    PLOT_HEIGHT = 10  # Number of vertical rows for the chart
    BAR_COLOR = "dodger_blue2"  # Consistent with memory and cpu_core widgets

    def __init__(
        self,
        history_window: int = 60,
        poll_interval: float = 2.0,
        **kwargs,
    ):
        """Initialize history plot widget.

        Args:
            history_window: Time window in seconds
            plot_style: Visualization style (kept for API compatibility)
            poll_interval: Polling interval in seconds
        """
        super().__init__(**kwargs)
        self.history_window = history_window
        self.poll_interval = poll_interval
        self._history_data: list[tuple[float, float]] = []
        # Calculate the number of bars based on history window and poll interval
        self._num_bars = max(1, int(history_window / poll_interval))
        # Start with zeros to fill the display area
        self._display_data: list[float] = [0.0] * self._num_bars

        logger.info(
            f"HistoryPlotWidget initialized with "
            f"history_window={history_window}s, poll_interval={poll_interval}s, "
            f"num_bars={self._num_bars}"
        )

    @property
    def history_data(self) -> list[tuple[float, float]]:
        """Get the history data (for backwards compatibility)."""
        return self._history_data

    @property
    def data(self) -> list[float]:
        """Get the display data (for backwards compatibility with tests)."""
        return self._display_data

    def update_history(self, history_data: list[tuple[float, float]]) -> None:
        """Update history data with sliding window effect.

        New data appears on the right, old data slides to the left.
        Always maintains _num_bars data points for consistent bar width.

        Args:
            history_data: List of (timestamp, usage) tuples
        """
        self._history_data = history_data
        data_points = len(history_data)

        if data_points > 0:
            time_span = (
                history_data[-1][0] - history_data[0][0] if data_points >= 2 else 0
            )
            logger.info(
                f"HistoryPlotWidget updated: {data_points} data points over {time_span:.1f}s"
            )

        # Extract just the usage values
        usages = [usage for _, usage in history_data]

        # Create display data with sliding window effect
        # Oldest data on left, newest on right
        if len(usages) >= self._num_bars:
            # Take the most recent _num_bars points
            # (oldest first/left, newest last/right)
            self._display_data = usages[-self._num_bars:]
        else:
            # Pad with zeros on the left, usages on the right (newest at end)
            self._display_data = [0.0] * (self._num_bars - len(usages)) + usages

        # Re-render the chart with new data
        self.refresh()

    def render(self) -> str:
        """Render the history plot as a simple multi-line string."""
        if not self._display_data:
            return "[dim]No data available[/dim]"

        lines = []

        # Build the chart - 10 rows from 100% (top) to 0% (bottom)
        for row in range(self.PLOT_HEIGHT):
            # Calculate threshold for this row (100% at top, 0% at bottom)
            threshold = 100.0 - (row * 100.0 / self.PLOT_HEIGHT)

            # Y-axis label (every other row for readability)
            if row % 2 == 0:
                y_label = f"{int(threshold):3d}%"
            else:
                y_label = "    "

            # Build the bar characters for this row
            bars = []
            for value in self._display_data:
                # Determine if this cell should be filled based on value
                next_threshold = 100.0 - ((row + 1) * 100.0 / self.PLOT_HEIGHT)
                if value >= threshold:
                    bars.append("█")
                elif value > next_threshold:
                    # Partial fill
                    bars.append("▄")
                else:
                    bars.append(" ")

            # Join bars and add color
            bar_line = "".join(bars)

            # Right Y-axis label (every other row for readability)
            if row % 2 == 0:
                y_label_right = f"{int(threshold):3d}%"
            else:
                y_label_right = "    "

            lines.append(f"{y_label}│[{self.BAR_COLOR}]{bar_line}[/{self.BAR_COLOR}]│{y_label_right}")

        # X-axis line
        x_axis = "    └" + "─" * len(self._display_data) + "┘"
        lines.append(x_axis)

        # Time labels
        time_label = f"    -{self.history_window}s{' ' * (len(self._display_data) - 6)}now"
        lines.append(time_label)

        return "\n".join(lines)
