"""TUI (Terminal User Interface) components for CPU monitoring."""

from typing import Optional, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal, Grid
from textual.widgets import Header, Footer, Static, Button, Input, Label
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.binding import Binding

from .monitor import ServerMetrics, CPUCore


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
        self._on_delete_server = on_delete_server
        self._on_add_server = on_add_server

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

    def _update_selection(self):
        """Update the selection state of all server widgets."""
        for i, widget in enumerate(self.server_widgets):
            widget.set_selected(i == self.selected_index)
