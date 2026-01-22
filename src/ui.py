"""TUI (Terminal User Interface) components for CPU monitoring."""

from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from textual.binding import Binding

from .monitor import ServerMetrics, CPUCore


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


class ServerWidget(Static):
    """Widget displaying a server and its CPU cores."""

    expanded = reactive(False)

    def __init__(
        self,
        server_name: str,
        low_threshold: float = 30.0,
        medium_threshold: float = 70.0,
        start_collapsed: bool = False,
        **kwargs,
    ):
        """Initialize server widget.

        Args:
            server_name: Name of the server
            low_threshold: Threshold for low usage
            medium_threshold: Threshold for medium usage
            start_collapsed: Whether to start in collapsed state
        """
        super().__init__(**kwargs)
        self.server_name = server_name
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.expanded = not start_collapsed

        self.metrics: Optional[ServerMetrics] = None
        self.core_widgets: list[CPUCoreWidget] = []
        self.header_widget: Optional[Static] = None
        self.cores_container: Optional[Vertical] = None
        self.is_selected = False

    def compose(self) -> ComposeResult:
        """Compose the server widget layout."""
        with Vertical():
            # Sanitize server name for use in widget IDs (replace spaces with hyphens)
            safe_id = self.server_name.replace(" ", "-")
            self.header_widget = Static("", id=f"header-{safe_id}")
            yield self.header_widget

            self.cores_container = Vertical(id=f"cores-{safe_id}")
            yield self.cores_container

    def on_mount(self):
        """Handle widget mount event."""
        self.refresh_display()

    def update_metrics(self, metrics: ServerMetrics):
        """Update server metrics.

        Args:
            metrics: Updated server metrics
        """
        self.metrics = metrics

        # Update or create core widgets
        if metrics.connected and metrics.cores:
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
                    if self.cores_container:
                        self.cores_container.mount(core_widget)

        self.refresh_display()

    def toggle_expanded(self):
        """Toggle expanded/collapsed state."""
        self.expanded = not self.expanded
        self.refresh_display()

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
            status = "[dim]Initializing...[/dim]"
        elif not self.metrics.connected:
            error = self.metrics.error_message or "Disconnected"
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

        # Show/hide cores
        if self.cores_container:
            self.cores_container.display = self.expanded


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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("left", "collapse", "Collapse", show=False),
        Binding("right", "expand", "Expand", show=False),
        Binding("enter", "toggle_expand", "Toggle", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("p", "command_palette", "Palette", show=True),
    ]

    def __init__(self, server_widgets: list[ServerWidget], **kwargs):
        """Initialize the monitoring app.

        Args:
            server_widgets: List of server widgets to display
        """
        super().__init__(**kwargs)
        self.server_widgets = server_widgets
        self.selected_index = 0
        self.main_container: Optional[VerticalScroll] = None

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=True)

        with VerticalScroll(id="main-container") as container:
            self.main_container = container
            for widget in self.server_widgets:
                yield widget

        yield Footer()

    def on_mount(self):
        """Handle app mount event."""
        self._update_selection()

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

    def _update_selection(self):
        """Update the selection state of all server widgets."""
        for i, widget in enumerate(self.server_widgets):
            widget.set_selected(i == self.selected_index)
