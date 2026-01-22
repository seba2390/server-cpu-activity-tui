"""TUI (Terminal User Interface) components for CPU monitoring."""

import time
from typing import Optional, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, Static, Button, Input, Label
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.binding import Binding

from .monitor import ServerMetrics, CPUCore, MemoryInfo


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal screen for confirming server deletion."""

    CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    #confirm-dialog Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    #confirm-buttons Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, server_name: str, **kwargs):
        super().__init__(**kwargs)
        self.server_name = server_name

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(f"Delete server '{self.server_name}'?")
            yield Label("This will remove the server from config.yaml")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (y)", variant="error", id="yes-btn")
                yield Button("No (n)", variant="primary", id="no-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes-btn")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class AddServerScreen(ModalScreen[Optional[dict]]):
    """Modal screen for adding a new server."""

    CSS = """
    AddServerScreen {
        align: center middle;
    }

    #add-dialog {
        width: 70;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    #add-dialog Label {
        margin-top: 1;
    }

    #add-dialog Input {
        margin-bottom: 1;
    }

    #add-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #add-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #add-buttons Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-dialog"):
            yield Label("Add New Server", id="add-title")
            yield Label("Name:")
            yield Input(placeholder="My Server", id="input-name")
            yield Label("Host (IP/hostname):")
            yield Input(placeholder="192.168.1.100", id="input-host")
            yield Label("Username:")
            yield Input(placeholder="ubuntu", id="input-username", value="ubuntu")
            yield Label("SSH Key Path:")
            yield Input(placeholder="~/.ssh/id_rsa", id="input-keypath", value="~/.ssh/id_rsa")
            with Horizontal(id="add-buttons"):
                yield Button("Add", variant="success", id="add-btn")
                yield Button("Cancel", variant="primary", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#input-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        host = self.query_one("#input-host", Input).value.strip()
        username = self.query_one("#input-username", Input).value.strip()
        key_path = self.query_one("#input-keypath", Input).value.strip()

        if not all([name, host, username, key_path]):
            self.notify("All fields are required", severity="error")
            return

        self.dismiss({
            "name": name,
            "host": host,
            "username": username,
            "key_path": key_path,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


class CPUCoreWidget(Static):
    """Widget displaying a single CPU core's usage."""

    usage_percent = reactive(0.0)

    def __init__(
        self, core: CPUCore, low_threshold: float = 30.0, medium_threshold: float = 70.0, **kwargs
    ):
        """Initialize CPU core widget.

        Args:
            core: CPU core data
            low_threshold: Threshold for low usage (green)
            medium_threshold: Threshold for medium usage (yellow)
        """
        super().__init__(**kwargs)
        self.core = core
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.usage_percent = core.usage_percent

    def update_core(self, core: CPUCore):
        """Update core data.

        Args:
            core: Updated CPU core data
        """
        self.core = core
        self.usage_percent = core.usage_percent
        self.refresh()

    def render(self) -> str:
        """Render the CPU core widget."""
        usage = self.usage_percent
        bar_width = 30
        filled = int((usage / 100.0) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Color coding based on usage
        if usage < self.low_threshold:
            color = "green"
        elif usage < self.medium_threshold:
            color = "yellow"
        else:
            color = "red"

        return f"  Core {self.core.core_id:2d}: [{color}]{bar}[/{color}] {usage:5.1f}%"

class MemoryWidget(Static):
    """Widget displaying memory usage."""

    def __init__(self, low_threshold: float = 30.0, medium_threshold: float = 70.0, **kwargs):
        """Initialize memory widget.

        Args:
            low_threshold: Threshold for low usage (green)
            medium_threshold: Threshold for medium usage (yellow)
        """
        super().__init__(**kwargs)
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.memory_info: Optional[MemoryInfo] = None

    def update_memory(self, memory_info: Optional[MemoryInfo]):
        """Update memory data.

        Args:
            memory_info: Updated memory information
        """
        self.memory_info = memory_info
        self.refresh()

    def render(self) -> str:
        """Render the memory widget."""
        if not self.memory_info:
            return "  Memory: [dim]No data available[/dim]"

        mem = self.memory_info
        usage = mem.usage_percent
        bar_width = 30
        filled = int((usage / 100.0) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Color coding based on usage
        if usage < self.low_threshold:
            color = "green"
        elif usage < self.medium_threshold:
            color = "yellow"
        else:
            color = "red"

        used_gb = mem.used_mb / 1024.0
        total_gb = mem.total_mb / 1024.0

        return f"  Memory: [{color}]{bar}[/{color}] {usage:5.1f}% ({used_gb:.1f}/{total_gb:.1f} GB)"


class HistoryPlotWidget(Static):
    """Widget displaying a time-series plot of CPU usage with enhanced visuals."""

    # Braille patterns for high-resolution plotting (2x4 dots per character)
    # Each character can represent 2 columns and 4 rows of data points
    BRAILLE_BASE = 0x2800
    BRAILLE_DOTS = [
        [0x01, 0x08],  # Row 0: dots 1, 4
        [0x02, 0x10],  # Row 1: dots 2, 5
        [0x04, 0x20],  # Row 2: dots 3, 6
        [0x40, 0x80],  # Row 3: dots 7, 8
    ]

    def __init__(self, history_window: int = 60, **kwargs):
        """Initialize history plot widget.

        Args:
            history_window: Time window in seconds
        """
        super().__init__(**kwargs)
        self.history_window = history_window
        self.history_data: list[tuple[float, float]] = []

    def update_history(self, history_data: list[tuple[float, float]]):
        """Update history data.

        Args:
            history_data: List of (timestamp, usage) tuples
        """
        self.history_data = history_data
        self.refresh()

    def _get_color_for_usage(self, usage: float) -> str:
        """Get color based on CPU usage level."""
        if usage < 30:
            return "green"
        elif usage < 50:
            return "green3"
        elif usage < 70:
            return "yellow"
        elif usage < 85:
            return "orange1"
        else:
            return "red"

    def _create_filled_area_plot(self, usages: list[float], width: int, height: int) -> list[str]:
        """Create a filled area chart with gradient coloring.

        Args:
            usages: List of usage percentages
            width: Plot width in characters
            height: Plot height in rows

        Returns:
            List of strings representing plot rows (top to bottom)
        """
        if not usages:
            return [" " * width] * height

        # Resample data to fit plot width
        if len(usages) > width:
            step = len(usages) / width
            sampled = [usages[int(i * step)] for i in range(width)]
        elif len(usages) < width:
            # Stretch data to fill width
            sampled = []
            for i in range(width):
                idx = int(i * len(usages) / width)
                sampled.append(usages[min(idx, len(usages) - 1)])
        else:
            sampled = usages

        # Block characters for smooth vertical fill
        fill_blocks = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # Create the plot grid (row 0 = top = 100%, row height-1 = bottom = 0%)
        rows = []
        for row in range(height):
            row_str = ""
            # Calculate the percentage range for this row
            row_top_pct = 100.0 * (height - row) / height
            row_bottom_pct = 100.0 * (height - row - 1) / height

            for col, usage in enumerate(sampled):
                # Use explicit blue color with rich markup
                if usage >= row_top_pct:
                    # Full block - usage is above this entire row
                    row_str += "[blue]█[/blue]"
                elif usage <= row_bottom_pct:
                    # Empty - usage is below this entire row
                    row_str += " "
                else:
                    # Partial fill - calculate which sub-block to use
                    fill_ratio = (usage - row_bottom_pct) / (row_top_pct - row_bottom_pct)
                    block_idx = int(fill_ratio * (len(fill_blocks) - 1))
                    block_idx = max(0, min(len(fill_blocks) - 1, block_idx))
                    row_str += f"[blue]{fill_blocks[block_idx]}[/blue]"

            rows.append(row_str)

        return rows

    def render(self) -> str:
        """Render the CPU history plot with enhanced visuals."""
        if not self.history_data or len(self.history_data) < 2:
            lines = []
            lines.append("  [dim]┌" + "─" * 52 + "┐[/dim]")
            for _ in range(6):
                lines.append("  [dim]│[/dim]" + " " * 52 + "[dim]│[/dim]")
            lines.append("  [dim]└" + "─" * 52 + "┘[/dim]")
            lines.append("  [dim italic]  Collecting data... waiting for samples[/dim italic]")
            return "\n".join(lines)

        # Plot parameters
        plot_width = 50
        plot_height = 6

        # Get usage values
        usages = [u for _, u in self.history_data]

        # Calculate statistics
        current_usage = usages[-1] if usages else 0
        avg_usage = sum(usages) / len(usages) if usages else 0
        max_usage = max(usages) if usages else 0
        min_usage = min(usages) if usages else 0

        # Time range
        time_range = int(self.history_data[-1][0] - self.history_data[0][0]) if self.history_data else 0

        # Create the filled area plot
        plot_rows = self._create_filled_area_plot(usages, plot_width, plot_height)

        # Build the complete plot with frame and Y-axis labels
        lines = []

        # Y-axis labels for each row
        y_labels = ["100%", " 80%", " 60%", " 40%", " 20%", "  0%"]

        # Top border with title indicating average utilization
        title = " AVG CPU UTILIZATION "
        left_border = "─" * ((plot_width - len(title)) // 2)
        right_border = "─" * (plot_width - len(title) - len(left_border))
        lines.append(f"  [dim]     ┌{left_border}[/dim][bold dodger_blue2]{title}[/bold dodger_blue2][dim]{right_border}┐[/dim]")

        # Plot rows with Y-axis
        for i, (label, row) in enumerate(zip(y_labels, plot_rows)):
            lines.append(f"  [dim]{label} │[/dim]{row}[dim]│[/dim]")

        # Bottom border
        lines.append(f"  [dim]     └{'─' * plot_width}┘[/dim]")

        # X-axis time labels
        time_label_left = f"-{time_range}s"
        time_label_right = "now"
        spacing = plot_width - len(time_label_left) - len(time_label_right)
        lines.append(f"  [dim]      {time_label_left}{' ' * spacing}{time_label_right}[/dim]")

        return "\n".join(lines)

class ServerWidget(Static):
    """Widget displaying a server and its CPU cores."""

    expanded = reactive(False)

    # Spinner animation frames
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        server_name: str,
        low_threshold: float = 30.0,
        medium_threshold: float = 70.0,
        start_collapsed: bool = False,
        history_window: int = 60,
        **kwargs,
    ):
        """Initialize server widget.

        Args:
            server_name: Name of the server
            low_threshold: Threshold for low usage
            medium_threshold: Threshold for medium usage
            start_collapsed: Whether to start in collapsed state
            history_window: Time window for history graph (seconds)
        """
        super().__init__(**kwargs)
        self.server_name = server_name
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.expanded = not start_collapsed
        self.history_window = history_window

        self.metrics: Optional[ServerMetrics] = None
        self.core_widgets: list[CPUCoreWidget] = []
        self.memory_widget: Optional[MemoryWidget] = None
        self.history_widget: Optional[HistoryPlotWidget] = None
        self.header_widget: Optional[Static] = None
        self.cores_container: Optional[Container] = None
        self.memory_container: Optional[Container] = None
        self.history_container: Optional[Container] = None
        self.is_selected = False
        self._spinner_index = 0
        self._connection_start_time: Optional[float] = None
        self._retry_count = 0

    def compose(self) -> ComposeResult:
        """Compose the server widget layout."""
        with Vertical():
            # Sanitize server name for use in widget IDs (replace spaces with hyphens)
            safe_id = self.server_name.replace(" ", "-")
            self.header_widget = Static("", id=f"header-{safe_id}")
            yield self.header_widget

            # Two-column layout: CPU cores on left, memory+history on right
            with Horizontal(id=f"content-{safe_id}", classes="content-layout"):
                # Left column: CPU Cores Section
                with Container(id=f"cores-{safe_id}", classes="section-container left-column") as self.cores_container:
                    yield Static("[bold cyan]━━━ CPU CORES ━━━[/bold cyan]", classes="section-header")
                    yield Container(id=f"cores-content-{safe_id}", classes="section-content")

                # Right column: Memory and History stacked vertically
                with Vertical(classes="right-column"):
                    # Memory Section with header
                    with Container(id=f"memory-{safe_id}", classes="section-container") as self.memory_container:
                        yield Static("[bold magenta]━━━ MEMORY ━━━[/bold magenta]", classes="section-header")
                        self.memory_widget = MemoryWidget(self.low_threshold, self.medium_threshold)
                        yield self.memory_widget

                    # History Section with header
                    with Container(id=f"history-{safe_id}", classes="section-container") as self.history_container:
                        yield Static("[bold yellow]━━━ CPU HISTORY ━━━[/bold yellow]", classes="section-header")
                        self.history_widget = HistoryPlotWidget(self.history_window)
                        yield self.history_widget

    def on_mount(self):
        """Handle widget mount event."""
        self.refresh_display()

    def update_metrics(self, metrics: ServerMetrics):
        """Update server metrics.

        Args:
            metrics: Updated server metrics
        """
        self.metrics = metrics

        # Track connection state changes
        if metrics.connected:
            self._connection_start_time = None
            self._retry_count = 0
        elif self._connection_start_time is None:
            self._connection_start_time = time.time()

        # Update or create core widgets
        if metrics.connected and metrics.cores:
            safe_id = self.server_name.replace(" ", "-")
            cores_content = self.query_one(f"#cores-content-{safe_id}")

            # Remove excess core widgets
            while len(self.core_widgets) > len(metrics.cores):
                widget = self.core_widgets.pop()
                widget.remove()

            # Update existing or add new core widgets
            for i, core in enumerate(metrics.cores):
                if i < len(self.core_widgets):
                    self.core_widgets[i].update_core(core)
                else:
                    core_widget = CPUCoreWidget(core, self.low_threshold, self.medium_threshold)
                    self.core_widgets.append(core_widget)
                    cores_content.mount(core_widget)

        # Update memory widget
        if self.memory_widget and metrics.connected:
            self.memory_widget.update_memory(metrics.memory)

        # Note: history will be updated separately via update_history method

        # Animate spinner for connecting state
        self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)
        self.refresh_display()

    def toggle_expanded(self):
        """Toggle expanded/collapsed state."""
        self.expanded = not self.expanded
        self.refresh_display()
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
        self.is_selected = selected
        self.refresh_display()

    def refresh_display(self):
        """Refresh the display of this widget."""
        if not self.header_widget:
            return

        # Build header
        expand_icon = "▼" if self.expanded else "▶"
        selection_marker = "→" if self.is_selected else " "

        if self.metrics is None:
            # Show animated spinner while initializing
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
            # Color code overall usage
            usage = self.metrics.overall_usage
            if usage < self.low_threshold:
                color = "green"
            elif usage < self.medium_threshold:
                color = "yellow"
            else:
                color = "red"

            core_count = self.metrics.core_count
            status = f"[{color}]✓ {usage:5.1f}% avg ({core_count} cores)[/{color}]"

        header_style = "bold" if self.is_selected else ""
        if header_style:
            header_text = f"[{header_style}]{selection_marker} {expand_icon} {self.server_name}: {status}[/{header_style}]"
        else:
            header_text = f"{selection_marker} {expand_icon} {self.server_name}: {status}"

        self.header_widget.update(header_text)

        # Show/hide all content sections based on expanded state
        if self.cores_container:
            self.cores_container.display = self.expanded
        if self.memory_container:
            self.memory_container.display = self.expanded
        if self.history_container:
            self.history_container.display = self.expanded


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

    def update_stats(
        self,
        total: int,
        connected: int,
        average_cpu: float,
        last_update_time: Optional[float] = None
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
            from datetime import datetime
            dt = datetime.fromtimestamp(last_update_time)
            self.last_update = dt.strftime("%H:%M:%S")
        else:
            self.last_update = "--:--:--"

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


class MonitoringApp(App):
    """Main TUI application for CPU monitoring."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
        overflow-y: auto;
    }

    ServerWidget {
        margin: 0 1;
        padding: 0;
        height: auto;
    }

    ServerWidget > Vertical {
        height: auto;
        padding: 0;
        margin: 0;
    }

    ServerWidget Vertical {
        height: auto;
    }

    CPUCoreWidget {
        padding: 0 1;
        height: auto;
    }

    MemoryWidget {
        padding: 0 1;
        height: auto;
    }

    HistoryPlotWidget {
        padding: 0 1;
        height: auto;
    }

    .content-layout {
        height: auto;
        width: 100%;
    }

    .left-column {
        width: 50%;
        height: auto;
    }

    .right-column {
        width: 50%;
        height: auto;
    }

    .section-container {
        height: auto;
        padding: 0;
        border: solid $primary;
        background: $surface;
    }

    .right-column .section-container {
        margin-left: 1;
        margin-top: 1;
    }

    .right-column .section-container:first-child {
        margin-top: 0;
    }

    .section-header {
        width: 100%;
        text-align: center;
        height: 1;
        background: $boost;
        padding: 0 1;
    }

    .section-content {
        height: auto;
        padding: 0;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("left", "collapse", "Collapse", show=False),
        Binding("right", "expand", "Expand", show=False),
        Binding("enter", "toggle_expand", "Toggle", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("a", "add_server", "Add", show=True),
        Binding("d", "delete_server", "Delete", show=True),
        Binding("p", "command_palette", "Palette", show=True),
    ]

    def __init__(
        self,
        server_widgets: list[ServerWidget],
        on_delete_server: Optional[Callable[[str], None]] = None,
        on_add_server: Optional[Callable[[dict], None]] = None,
        **kwargs
    ):
        """Initialize the monitoring app.

        Args:
            server_widgets: List of server widgets to display
            on_delete_server: Callback when a server is deleted (receives server name)
            on_add_server: Callback when a server is added (receives server config dict)
        """
        super().__init__(**kwargs)
        self.server_widgets = server_widgets
        self.selected_index = 0
        self.main_container: Optional[VerticalScroll] = None
        self.status_bar: Optional[StatusBar] = None
        self._on_delete_server = on_delete_server
        self._on_add_server = on_add_server
        self._last_metrics_update: Optional[float] = None

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=True)

        with VerticalScroll(id="main-container") as container:
            self.main_container = container
            for widget in self.server_widgets:
                yield widget

        self.status_bar = StatusBar(id="status-bar")
        yield self.status_bar
        yield Footer()

    def on_mount(self):
        """Handle app mount event."""
        self._update_selection()
        self._update_status_bar()

    def action_navigate_up(self):
        """Navigate to previous server."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._update_selection()

    def action_navigate_down(self):
        """Navigate to next server."""
        if self.selected_index < len(self.server_widgets) - 1:
            self.selected_index += 1
            self._update_selection()

    def action_toggle_expand(self):
        """Toggle expanded/collapsed state of selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            self.server_widgets[self.selected_index].toggle_expanded()

    def action_expand(self):
        """Expand selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            if not widget.expanded:
                widget.toggle_expanded()

    def action_collapse(self):
        """Collapse selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            if widget.expanded:
                widget.toggle_expanded()

    def action_refresh(self):
        """Force refresh of all displays."""
        for widget in self.server_widgets:
            widget.refresh_display()
        self._update_status_bar()

    def action_delete_server(self):
        """Delete the selected server."""
        if not self.server_widgets:
            self.notify("No servers to delete", severity="warning")
            return

        if 0 <= self.selected_index < len(self.server_widgets):
            server_name = self.server_widgets[self.selected_index].server_name
            self.push_screen(ConfirmDeleteScreen(server_name), self._handle_delete_confirm)

    def _handle_delete_confirm(self, confirmed: bool) -> None:
        """Handle delete confirmation result."""
        if confirmed and 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            server_name = widget.server_name

            # Remove widget from list and UI
            self.server_widgets.pop(self.selected_index)
            widget.remove()

            # Adjust selection
            if self.selected_index >= len(self.server_widgets):
                self.selected_index = max(0, len(self.server_widgets) - 1)

            self._update_selection()

            # Callback to main app to persist changes
            if self._on_delete_server:
                self._on_delete_server(server_name)

            self.notify(f"Server '{server_name}' deleted", severity="information")

    def action_add_server(self):
        """Add a new server."""
        self.push_screen(AddServerScreen(), self._handle_add_server)

    def _handle_add_server(self, server_config: Optional[dict]) -> None:
        """Handle add server result."""
        if server_config:
            # Callback to main app to create components and persist
            if self._on_add_server:
                self._on_add_server(server_config)
            self.notify(f"Server '{server_config['name']}' added", severity="information")

    def add_server_widget(self, widget: ServerWidget) -> None:
        """Add a new server widget to the UI.

        Args:
            widget: The server widget to add
        """
        self.server_widgets.append(widget)
        if self.main_container:
            self.main_container.mount(widget)
        self.selected_index = len(self.server_widgets) - 1
        self._update_selection()
        self._update_status_bar()

    def _update_selection(self):
        """Update the selection state of all server widgets."""
        for i, widget in enumerate(self.server_widgets):
            widget.set_selected(i == self.selected_index)

    def _update_status_bar(self):
        """Update status bar with current statistics."""
        if not self.status_bar:
            return

        total = len(self.server_widgets)
        connected = 0
        total_cpu = 0.0
        cpu_count = 0

        for widget in self.server_widgets:
            if widget.metrics and widget.metrics.connected:
                connected += 1
                total_cpu += widget.metrics.overall_usage
                cpu_count += 1

        average_cpu = total_cpu / cpu_count if cpu_count > 0 else 0.0

        self.status_bar.update_stats(
            total=total,
            connected=connected,
            average_cpu=average_cpu,
            last_update_time=self._last_metrics_update
        )

    def update_metrics_timestamp(self):
        """Update the timestamp of last metrics update."""
        self._last_metrics_update = time.time()
        self._update_status_bar()
