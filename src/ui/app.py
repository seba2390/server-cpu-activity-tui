"""Main TUI application for CPU monitoring."""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header

from .messages import ServerAdded, ServerDeleted
from .screens import AddServerScreen, ConfirmDeleteScreen
from .widgets import ServerWidget, StatusBar

if TYPE_CHECKING:
    from ..main import ServerConfigDict

logger = logging.getLogger(__name__)


class MonitoringApp(App[None]):
    """Main TUI application for CPU monitoring."""

    CSS_PATH = Path(__file__).parent / "app.tcss"

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
        on_delete_server: Callable[[str], None] | None = None,
        on_add_server: Callable[["ServerConfigDict"], None] | None = None,
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
        self.main_container: VerticalScroll | None = None
        self.status_bar: StatusBar | None = None
        self._on_delete_server = on_delete_server
        self._on_add_server = on_add_server
        self._last_metrics_update: float | None = None
        logger.info(f"MonitoringApp initialized with {len(server_widgets)} server widgets")

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=True)

        with VerticalScroll(id="main-container") as container:
            self.main_container = container
            yield from self.server_widgets

        self.status_bar = StatusBar(id="status-bar")
        yield self.status_bar
        yield Footer()

    def on_mount(self):
        """Handle app mount event."""
        logger.info("MonitoringApp mounted, initializing UI state")
        self._update_selection()
        self._update_status_bar()

    def action_navigate_up(self):
        """Navigate to previous server."""
        if self.selected_index > 0:
            old_index = self.selected_index
            self.selected_index -= 1
            logger.info(f"Navigation: moved up from index {old_index} to {self.selected_index}")
            self._update_selection()

    def action_navigate_down(self):
        """Navigate to next server."""
        if self.selected_index < len(self.server_widgets) - 1:
            old_index = self.selected_index
            self.selected_index += 1
            logger.info(f"Navigation: moved down from index {old_index} to {self.selected_index}")
            self._update_selection()

    def action_toggle_expand(self):
        """Toggle expanded/collapsed state of selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            server_name = self.server_widgets[self.selected_index].server_name
            logger.info(f"User action: toggle_expand for server '{server_name}'")
            self.server_widgets[self.selected_index].toggle_expanded()

    def action_expand(self):
        """Expand selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            if not widget.expanded:
                logger.info(f"User action: expand server '{widget.server_name}'")
                widget.toggle_expanded()

    def action_collapse(self):
        """Collapse selected server."""
        if 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            if widget.expanded:
                logger.info(f"User action: collapse server '{widget.server_name}'")
                widget.toggle_expanded()

    def action_refresh(self):
        """Force refresh of all displays."""
        logger.info(f"User action: manual refresh requested for {len(self.server_widgets)} servers")
        for widget in self.server_widgets:
            widget.refresh_display()
        self._update_status_bar()

    def action_delete_server(self):
        """Delete the selected server."""
        if not self.server_widgets:
            logger.warning("User attempted to delete server but no servers exist")
            self.notify("No servers to delete", severity="warning")
            return

        if 0 <= self.selected_index < len(self.server_widgets):
            server_name = self.server_widgets[self.selected_index].server_name
            logger.info(f"User action: delete_server initiated for '{server_name}'")
            self.push_screen(ConfirmDeleteScreen(server_name), self._handle_delete_confirm)

    def _handle_delete_confirm(self, confirmed: bool | None) -> None:
        """Handle delete confirmation result."""
        if confirmed and 0 <= self.selected_index < len(self.server_widgets):
            widget = self.server_widgets[self.selected_index]
            server_name = widget.server_name

            logger.info(f"Deleting server '{server_name}' from UI (index {self.selected_index})")

            # Remove widget from list and UI
            self.server_widgets.pop(self.selected_index)
            widget.remove()

            # Adjust selection
            old_index = self.selected_index
            if self.selected_index >= len(self.server_widgets):
                self.selected_index = max(0, len(self.server_widgets) - 1)

            logger.info(f"Server deleted, adjusted selection from index {old_index} to {self.selected_index}")
            self._update_selection()

            # Post message for Textual-idiomatic handling
            self.post_message(ServerDeleted(server_name))

            # Legacy callback support for backwards compatibility
            if self._on_delete_server:
                logger.info(f"Invoking delete callback for server '{server_name}'")
                self._on_delete_server(server_name)

            self.notify(f"Server '{server_name}' deleted", severity="success")
        elif not confirmed:
            logger.info("Server deletion was not confirmed by user")

    def action_add_server(self):
        """Add a new server."""
        logger.info("User action: add_server initiated, opening AddServerScreen")
        self.push_screen(AddServerScreen(), self._handle_add_server)

    def _handle_add_server(self, server_config: "ServerConfigDict | None") -> None:
        """Handle add server result."""
        if server_config:
            logger.info(f"Add server confirmed: {server_config['name']} ({server_config['host']})")

            # Post message for Textual-idiomatic handling
            self.post_message(ServerAdded(server_config))

            # Legacy callback support for backwards compatibility
            if self._on_add_server:
                logger.info(f"Invoking add callback for server '{server_config['name']}'")
                self._on_add_server(server_config)
            self.notify(f"Server '{server_config['name']}' added", severity="success")
        else:
            logger.info("Add server cancelled by user")

    def add_server_widget(self, widget: ServerWidget) -> None:
        """Add a new server widget to the UI.

        Args:
            widget: The server widget to add
        """
        logger.info(f"Adding server widget to UI: {widget.server_name}")
        self.server_widgets.append(widget)
        if self.main_container:
            self.main_container.mount(widget)
        self.selected_index = len(self.server_widgets) - 1
        logger.info(f"Server widget added, total servers: {len(self.server_widgets)}, selected_index: {self.selected_index}")
        self._update_selection()
        self._update_status_bar()

    def _update_selection(self):
        """Update the selection state of all server widgets."""
        if 0 <= self.selected_index < len(self.server_widgets):
            selected_name = self.server_widgets[self.selected_index].server_name
            logger.info(f"Selection updated: index={self.selected_index}, server='{selected_name}'")
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
        logger.info(f"Metrics timestamp updated: {time.strftime('%H:%M:%S', time.localtime(self._last_metrics_update))}")
        self._update_status_bar()
