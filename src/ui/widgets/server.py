"""Widget displaying a server and its CPU cores."""

import logging
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from .cpu_core import CPUCoreWidget
from .history_plot import HistoryPlotWidget
from .memory import MemoryWidget
from ...monitor import ServerMetrics

logger = logging.getLogger(__name__)


class ServerWidget(Static):
    """Widget displaying a server and its CPU cores."""

    # Use init=False to prevent watcher from firing before widget is fully initialized
    expanded = reactive(False, init=False)

    # Spinner animation frames
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        server_name: str,
        history_window: int = 60,
        plot_style: str = "braille",
        poll_interval: float = 2.0,
        **kwargs,
    ):
        """Initialize server widget.

        Args:
            server_name: Name of the server
            history_window: Time window for history graph (seconds)
            plot_style: Visualization style for CPU history plot
            poll_interval: Polling interval in seconds
        """
        super().__init__(**kwargs)
        self.server_name = server_name
        self.history_window = history_window
        self.plot_style = plot_style
        self.poll_interval = poll_interval

        self.metrics: ServerMetrics | None = None
        self.core_widgets: list[CPUCoreWidget] = []
        self.memory_widget: MemoryWidget | None = None
        self.history_widget: HistoryPlotWidget | None = None
        self.header_widget: Static | None = None
        self.content_layout: Horizontal | None = None  # Main content container
        self.is_selected = False
        self._spinner_index = 0
        self._connection_start_time: float | None = None
        self._retry_count = 0

        # Set expanded after all attributes are initialized (watcher-safe)
        self.expanded = False  # Always start collapsed

    def compose(self) -> ComposeResult:
        """Compose the server widget layout."""
        # Sanitize server name for use in widget IDs (replace spaces with hyphens)
        safe_id = self.server_name.replace(" ", "-")

        self.header_widget = Static("", id=f"header-{safe_id}", classes="server-header")
        yield self.header_widget

        # Two-column layout using Horizontal with Vertical columns (following Textual patterns)
        with Horizontal(id=f"content-{safe_id}", classes="content-layout") as self.content_layout:
            # Left column: CPU Cores Section
            with Vertical(id=f"cores-{safe_id}", classes="left-column"):
                yield Static("CPU CORES", classes="section-header")
                yield Vertical(id=f"cores-content-{safe_id}", classes="section-content")

            # Right column: Memory and History stacked vertically
            with Vertical(classes="right-column"):
                # Memory Section with header
                with Vertical(id=f"memory-{safe_id}", classes="section-container"):
                    yield Static("MEMORY", classes="section-header")
                    self.memory_widget = MemoryWidget()
                    yield self.memory_widget

                # History Section with header
                with Vertical(id=f"history-{safe_id}", classes="section-container"):
                    yield Static("CPU HISTORY", classes="section-header")
                    self.history_widget = HistoryPlotWidget(
                        self.history_window,
                        self.poll_interval
                    )
                    yield self.history_widget

    def on_mount(self):
        """Handle widget mount event."""
        logger.info(f"ServerWidget mounted: {self.server_name}")
        # Start spinner animation timer (0.1s interval for smooth animation)
        self._spinner_timer = self.set_interval(0.1, self._animate_spinner)
        self.refresh_display()

    def _animate_spinner(self) -> None:
        """Advance the spinner animation frame.

        This is called by the timer to animate the spinner independently
        of the UI update loop.
        """
        # Only animate if we're showing a spinner (not connected)
        if self.metrics is None or not self.metrics.connected:
            self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)
            self._update_header()

    def update_metrics(self, metrics: ServerMetrics):
        """Update server metrics.

        Args:
            metrics: Updated server metrics
        """
        logger.info(f"ServerWidget updating metrics: server={self.server_name}, connected={metrics.connected}, cores={len(metrics.cores)}, overall_usage={metrics.overall_usage:.1f}%")

        self.metrics = metrics

        # Track connection state changes
        if metrics.connected:
            if self._connection_start_time is not None:
                elapsed = time.time() - self._connection_start_time
                logger.info(f"Server '{self.server_name}' connected successfully after {elapsed:.1f}s")
            self._connection_start_time = None
            self._retry_count = 0
        elif self._connection_start_time is None:
            logger.warning(f"Server '{self.server_name}' disconnected: {metrics.error_message}")
            self._connection_start_time = time.time()

        # Update or create core widgets
        if metrics.connected and metrics.cores:
            safe_id = self.server_name.replace(" ", "-")
            cores_content = self.query_one(f"#cores-content-{safe_id}")

            # Remove excess core widgets
            removed_count = 0
            while len(self.core_widgets) > len(metrics.cores):
                widget = self.core_widgets.pop()
                widget.remove()
                removed_count += 1
            if removed_count > 0:
                logger.info(f"ServerWidget '{self.server_name}': removed {removed_count} excess core widgets")

            # Update existing or add new core widgets
            added_count = 0
            for i, core in enumerate(metrics.cores):
                if i < len(self.core_widgets):
                    self.core_widgets[i].update_core(core)
                else:
                    core_widget = CPUCoreWidget(core)
                    self.core_widgets.append(core_widget)
                    cores_content.mount(core_widget)
                    added_count += 1
            if added_count > 0:
                logger.info(f"ServerWidget '{self.server_name}': added {added_count} new core widgets")

        # Update memory widget
        if self.memory_widget and metrics.connected:
            self.memory_widget.update_memory(metrics.memory)

        # Note: history will be updated separately via update_history method

        # Refresh display to update UI
        self.refresh_display()

    def toggle_expanded(self):
        """Toggle expanded/collapsed state."""
        self.expanded = not self.expanded
        logger.info(f"ServerWidget '{self.server_name}' toggled: expanded={self.expanded}")

    def watch_expanded(self, expanded: bool) -> None:
        """Called automatically when the expanded reactive property changes.

        Args:
            expanded: The new expanded state
        """
        # Show/hide the entire content layout based on expanded state
        if self.content_layout:
            self.content_layout.display = expanded
        # Update header to reflect new state
        self._update_header()

    def update_history(self, history_data: list[tuple[float, float]]):
        """Update CPU history data.

        Args:
            history_data: List of (timestamp, usage) tuples
        """
        if self.history_widget:
            self.history_widget.update_history(history_data)

    def set_selected(self, selected: bool):
        """Set selection state.

        Args:
            selected: Whether this server is selected
        """
        if selected != self.is_selected:
            logger.info(f"ServerWidget '{self.server_name}' selection changed: {selected}")
        self.is_selected = selected
        self._update_header()

    def _update_header(self) -> None:
        """Update the header widget with current state."""
        if not self.header_widget:
            return

        # Build header
        expand_icon = "▼" if self.expanded else "▶"
        selection_marker = "→" if self.is_selected else " "

        if self.metrics is None:
            # Spinner animation is handled by _animate_spinner timer
            spinner = self.SPINNER_FRAMES[self._spinner_index]
            status = f"[cyan]{spinner} Initializing...[/cyan]"
        elif not self.metrics.connected:
            # Show spinner with error and elapsed time
            spinner = self.SPINNER_FRAMES[self._spinner_index]
            error = self.metrics.error_message or "Disconnected"

            # Calculate elapsed time if connecting
            if self._connection_start_time:
                elapsed = int(time.time() - self._connection_start_time)
                status = f"[yellow]{spinner} Connecting... ({elapsed}s) - {error}[/yellow]"
            else:
                status = f"[red]✗ {error}[/red]"
        else:
            # Use consistent blue color
            usage = self.metrics.overall_usage
            color = "dodger_blue2"

            core_count = self.metrics.core_count
            status = f"[{color}]✓ {usage:5.1f}% avg ({core_count} cores)[/{color}]"

        header_style = "bold" if self.is_selected else ""
        if header_style:
            header_text = f"[{header_style}]{selection_marker} {expand_icon} {self.server_name}: {status}[/{header_style}]"
        else:
            header_text = f"{selection_marker} {expand_icon} {self.server_name}: {status}"

        self.header_widget.update(header_text)

    def refresh_display(self):
        """Refresh the display of this widget.

        This method updates the header and container visibility.
        Called by external code (e.g., UI update loop) to refresh the display.
        """
        self._update_header()
        # Container visibility is handled by watch_expanded, but we update here
        # as well for cases where refresh_display is called externally
        if self.content_layout:
            self.content_layout.display = self.expanded
