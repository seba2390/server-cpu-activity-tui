"""TUI (Terminal User Interface) components for CPU monitoring."""

import logging
import time
from typing import Optional, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, Static, Button, Input, Label, OptionList, Select
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.binding import Binding

from .monitor import ServerMetrics, CPUCore, MemoryInfo

logger = logging.getLogger(__name__)


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
        logger.info(f"ConfirmDeleteScreen initialized for server: {server_name}")

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(f"Delete server '{self.server_name}'?")
            yield Label("This will remove the server from config.yaml")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (y)", variant="error", id="yes-btn")
                yield Button("No (n)", variant="primary", id="no-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        confirmed = event.button.id == "yes-btn"
        logger.info(f"Delete confirmation for '{self.server_name}': {'confirmed' if confirmed else 'cancelled'}")
        self.dismiss(confirmed)

    def action_confirm(self) -> None:
        logger.info(f"Delete confirmed via keyboard (y) for server: {self.server_name}")
        self.dismiss(True)

    def action_cancel(self) -> None:
        logger.info(f"Delete cancelled via keyboard (n/escape) for server: {self.server_name}")
        self.dismiss(False)


class AddServerScreen(ModalScreen[Optional[dict]]):
    """Modal screen for adding a new server with arrow key navigation."""

    CSS = """
    AddServerScreen {
        align: center middle;
    }

    #add-dialog {
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: $surface;
        border: double $primary;
    }

    #add-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        padding: 1;
        background: $boost;
    }

    .field-container {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }

    .field-label {
        color: $text;
        text-style: bold;
        margin-bottom: 0;
    }

    .field-label.highlighted {
        color: $accent;
    }

    .field-container Input {
        margin-top: 0;
        width: 100%;
    }

    .field-container Input:disabled {
        opacity: 0.6;
    }

    .field-container OptionList {
        height: 5;
        margin-top: 0;
        border: solid $primary;
    }

    .help-text {
        color: $text-muted;
        text-style: italic;
        margin-top: 0;
    }

    #add-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 2;
    }

    #add-buttons Button {
        margin: 0 2;
        min-width: 12;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Submit"),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("enter", "enter_field", "Enter", show=False),
        Binding("right", "enter_field", "Enter", show=False),
        Binding("left", "exit_field", "Exit", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auth_method = "key"  # Default authentication method
        self.fields = []  # List of field definitions
        self.current_field_index = 0
        self.in_edit_mode = False
        logger.info("AddServerScreen initialized with two-level navigation")

    def compose(self) -> ComposeResult:
        with Vertical(id="add-dialog"):
            yield Label("Add New Server", id="add-title")

            # Server Name Field
            with Vertical(classes="field-container", id="field-name"):
                yield Label("Server Name:", classes="field-label", id="label-name")
                yield Input(placeholder="e.g., Production Server 1", id="input-name", disabled=True)
                yield Label("A friendly name to identify this server", classes="help-text")

            # Host Field
            with Vertical(classes="field-container", id="field-host"):
                yield Label("Host (IP or Hostname):", classes="field-label", id="label-host")
                yield Input(placeholder="e.g., 192.168.1.100 or server.example.com", id="input-host", disabled=True)
                yield Label("The IP address or hostname of the server", classes="help-text")

            # Username Field
            with Vertical(classes="field-container", id="field-username"):
                yield Label("Username:", classes="field-label", id="label-username")
                yield Input(placeholder="e.g., ubuntu, admin, root", id="input-username", value="ubuntu", disabled=True)
                yield Label("SSH username for authentication", classes="help-text")

            # Authentication Method Selection
            with Vertical(classes="field-container", id="field-authmethod"):
                yield Label("Authentication Method:", classes="field-label", id="label-authmethod")
                auth_list = OptionList(
                    Option("SSH Key (recommended)", id="key"),
                    Option("Password", id="password"),
                    id="auth-method-list",
                    disabled=True
                )
                yield auth_list
                yield Label("Use ↑↓ to navigate, → or Enter to select", classes="help-text")

            # SSH Key Path Field (shown for key auth)
            with Vertical(classes="field-container", id="key-container"):
                yield Label("SSH Key Path:", classes="field-label", id="label-keypath")
                yield Input(placeholder="e.g., ~/.ssh/id_rsa", id="input-keypath", value="~/.ssh/id_rsa", disabled=True)
                yield Label("Path to your private SSH key file", classes="help-text")

            # Password Field (hidden by default, shown for password auth)
            with Vertical(classes="field-container hidden", id="password-container"):
                yield Label("Password:", classes="field-label", id="label-password")
                yield Input(placeholder="Enter password", id="input-password", password=True, disabled=True)
                yield Label("SSH password for authentication", classes="help-text")

            # Action Buttons
            with Horizontal(id="add-buttons"):
                yield Button("Add Server (Ctrl+S)", variant="success", id="add-btn")
                yield Button("Cancel (Esc)", variant="primary", id="cancel-btn")

    def on_mount(self) -> None:
        """Set up initial state when screen is mounted."""
        logger.info("AddServerScreen mounted, setting up initial state")

        # Define fields in order
        self.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
            {"id": "input-username", "label_id": "label-username", "type": "input"},
            {"id": "auth-method-list", "label_id": "label-authmethod", "type": "optionlist"},
            {"id": "input-keypath", "label_id": "label-keypath", "type": "input", "auth_type": "key"},
            {"id": "input-password", "label_id": "label-password", "type": "input", "auth_type": "password"},
            {"id": "add-btn", "label_id": None, "type": "button"},
        ]

        # Select the first auth method (SSH Key) by default
        auth_list = self.query_one("#auth-method-list", OptionList)
        auth_list.highlighted = 0

        # Start in navigation mode, highlight first field
        self.current_field_index = 0
        self.in_edit_mode = False
        self._update_field_highlights()

        logger.info("Two-level navigation initialized - use ↑↓ to navigate, → or Enter to edit")

    def _update_field_highlights(self) -> None:
        """Update visual indicators to show which field is highlighted."""
        # Define original label texts
        label_texts = {
            "label-name": "Server Name:",
            "label-host": "Host (IP or Hostname):",
            "label-username": "Username:",
            "label-authmethod": "Authentication Method:",
            "label-keypath": "SSH Key Path:",
            "label-password": "Password:",
        }

        # Reset all labels to original text without arrows
        for label_id, text in label_texts.items():
            try:
                label = self.query_one(f"#{label_id}", Label)
                label.update(text)
                label.remove_class("highlighted")
            except:
                pass  # Label might not exist yet

        # Get current field
        field = self._get_current_field()
        if not field:
            return

        # Skip if this field shouldn't be shown based on auth method
        if "auth_type" in field and field["auth_type"] != self.auth_method:
            # Move to next valid field
            self._navigate_to_next_valid_field()
            return

        # Add arrow and highlight to current field label
        if field["label_id"] and field["label_id"] in label_texts:
            label = self.query_one(f"#{field['label_id']}", Label)
            label.add_class("highlighted")
            original_text = label_texts[field["label_id"]]

            # Update label text to include arrow
            if self.in_edit_mode:
                label.update(f"▶ {original_text}")
            else:
                label.update(f"→ {original_text}")

        logger.info(f"Highlighted field {field['id']}, edit_mode={self.in_edit_mode}")

    def _get_current_field(self):
        """Get the current field definition."""
        if 0 <= self.current_field_index < len(self.fields):
            return self.fields[self.current_field_index]
        return None

    def _navigate_to_next_valid_field(self):
        """Move to the next field that should be displayed."""
        original_index = self.current_field_index
        max_attempts = len(self.fields)
        attempts = 0

        while attempts < max_attempts:
            self.current_field_index = (self.current_field_index + 1) % len(self.fields)
            field = self._get_current_field()

            # Check if this field should be shown
            if "auth_type" not in field or field["auth_type"] == self.auth_method:
                self._update_field_highlights()
                return

            attempts += 1

        # If we couldn't find a valid field, stay where we were
        self.current_field_index = original_index

    def _navigate_to_prev_valid_field(self):
        """Move to the previous field that should be displayed."""
        original_index = self.current_field_index
        max_attempts = len(self.fields)
        attempts = 0

        while attempts < max_attempts:
            self.current_field_index = (self.current_field_index - 1) % len(self.fields)
            field = self._get_current_field()

            # Check if this field should be shown
            if "auth_type" not in field or field["auth_type"] == self.auth_method:
                self._update_field_highlights()
                return

            attempts += 1

        # If we couldn't find a valid field, stay where we were
        self.current_field_index = original_index

    def action_navigate_up(self) -> None:
        """Navigate to previous field (only in navigation mode)."""
        if self.in_edit_mode:
            return  # Arrow keys are for editing

        self._navigate_to_prev_valid_field()
        logger.info(f"Navigated up to field index {self.current_field_index}")

    def action_navigate_down(self) -> None:
        """Navigate to next field (only in navigation mode)."""
        if self.in_edit_mode:
            return  # Arrow keys are for editing

        self._navigate_to_next_valid_field()
        logger.info(f"Navigated down to field index {self.current_field_index}")

    def action_enter_field(self) -> None:
        """Enter edit mode for current field (Enter or Right arrow)."""
        if self.in_edit_mode:
            # If already in edit mode, Enter exits (for inputs) or confirms (for buttons)
            self.action_exit_field()
            return

        field = self._get_current_field()
        if not field:
            return

        # Enter edit mode
        self.in_edit_mode = True

        if field["type"] == "input":
            widget = self.query_one(f"#{field['id']}", Input)
            widget.disabled = False
            widget.focus()
        elif field["type"] == "optionlist":
            widget = self.query_one(f"#{field['id']}", OptionList)
            widget.disabled = False
            widget.focus()
        elif field["type"] == "button":
            # Buttons are activated immediately
            self.in_edit_mode = False
            button = self.query_one(f"#{field['id']}", Button)
            self.on_button_pressed(Button.Pressed(button))
            return

        self._update_field_highlights()
        logger.info(f"Entered edit mode for field {field['id']}")

    def action_exit_field(self) -> None:
        """Exit edit mode (Left arrow or Enter)."""
        if not self.in_edit_mode:
            return

        field = self._get_current_field()
        if not field:
            return

        # Exit edit mode
        self.in_edit_mode = False

        if field["type"] == "input":
            widget = self.query_one(f"#{field['id']}", Input)
            widget.disabled = True
            widget.blur()
            # Return focus to the screen
            self.focus()
        elif field["type"] == "optionlist":
            widget = self.query_one(f"#{field['id']}", OptionList)
            widget.disabled = True
            widget.blur()
            # Return focus to the screen
            self.focus()

        self._update_field_highlights()
        logger.info(f"Exited edit mode for field {field['id']}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key pressed in an Input field."""
        # Pressing Enter in an input field should exit edit mode
        if self.in_edit_mode:
            self.action_exit_field()
            event.stop()  # Prevent further propagation

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle authentication method selection."""
        if event.option_list.id == "auth-method-list":
            self.auth_method = event.option.id
            logger.info(f"Authentication method changed to: {self.auth_method}")
            self._update_auth_fields()

            # Exit edit mode and move to next field
            self.action_exit_field()
            self._navigate_to_next_valid_field()
            logger.info(f"Auth method selected, moved to next field")

    def _update_auth_fields(self) -> None:
        """Show/hide authentication fields based on selected method."""
        key_container = self.query_one("#key-container")
        password_container = self.query_one("#password-container")

        if self.auth_method == "key":
            key_container.remove_class("hidden")
            password_container.add_class("hidden")
            logger.info("Showing SSH key field, hiding password field")
        else:
            key_container.add_class("hidden")
            password_container.remove_class("hidden")
            logger.info("Showing password field, hiding SSH key field")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "add-btn":
            logger.info("Add server button pressed, submitting form")
            self._submit()
        else:
            logger.info("Add server cancelled via button")
            self.dismiss(None)

    def action_submit(self) -> None:
        """Handle Ctrl+S keyboard shortcut to submit."""
        logger.info("Add server submitted via keyboard shortcut (Ctrl+S)")
        self._submit()

    def action_cancel(self) -> None:
        """Handle Escape key to cancel."""
        logger.info("Add server cancelled via keyboard (Escape)")
        self.dismiss(None)

    def _submit(self) -> None:
        """Validate and submit the form."""
        name = self.query_one("#input-name", Input).value.strip()
        host = self.query_one("#input-host", Input).value.strip()
        username = self.query_one("#input-username", Input).value.strip()

        logger.info(f"Add server form submitted: name={name}, host={host}, username={username}, auth_method={self.auth_method}")

        # Validate required fields
        if not name:
            logger.warning("Add server form submission failed: missing server name")
            self.notify("Server name is required", severity="error")
            self.query_one("#input-name", Input).focus()
            return

        if not host:
            logger.warning("Add server form submission failed: missing host")
            self.notify("Host (IP or hostname) is required", severity="error")
            self.query_one("#input-host", Input).focus()
            return

        if not username:
            logger.warning("Add server form submission failed: missing username")
            self.notify("Username is required", severity="error")
            self.query_one("#input-username", Input).focus()
            return

        # Build server config with auth_method
        server_config = {
            "name": name,
            "host": host,
            "username": username,
            "auth_method": self.auth_method,
        }

        # Validate authentication-specific fields
        if self.auth_method == "key":
            key_path = self.query_one("#input-keypath", Input).value.strip()
            if not key_path:
                logger.warning("Key path required for key authentication")
                self.notify("SSH key path is required for key authentication", severity="error")
                self.query_one("#input-keypath", Input).focus()
                return

            server_config["key_path"] = key_path
        else:
            # For password auth, collect password but DON'T save it to config
            # It will be stored in memory only (passed to add_server callback)
            password = self.query_one("#input-password", Input).value
            if not password:
                logger.warning("Password required for password authentication")
                self.notify("Password is required for password authentication", severity="error")
                self.query_one("#input-password", Input).focus()
                return

            # Pass password in memory, but it won't be saved to config file
            server_config["_password"] = password  # Temporary key for in-memory use

        logger.info(f"Server configuration validated successfully: {name}")

        self.notify(f"Adding server '{name}'...", severity="information")
        self.dismiss(server_config)


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
        logger.info(f"MemoryWidget initialized with thresholds: low={low_threshold}%, medium={medium_threshold}%")

    def update_memory(self, memory_info: Optional[MemoryInfo]):
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

    def __init__(self, history_window: int = 60, plot_style: str = "braille",
                 low_threshold: float = 30.0, medium_threshold: float = 70.0,
                 poll_interval: float = 2.0, **kwargs):
        """Initialize history plot widget.

        Args:
            history_window: Time window in seconds
            plot_style: Visualization style (area, gradient, braille, sparkline, layered)
            low_threshold: CPU usage threshold for low/medium boundary
            medium_threshold: CPU usage threshold for medium/high boundary
            poll_interval: Polling interval in seconds
        """
        super().__init__(**kwargs)
        self.history_window = history_window
        self.plot_style = plot_style
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.poll_interval = poll_interval
        self.history_data: list[tuple[float, float]] = []

        # Calculate plot width based on history_window and poll_interval
        # Each braille character shows 2 data points, so width = num_points / 2
        num_data_points = int(history_window / poll_interval)
        self.plot_width = num_data_points // 2  # 2 dots per character

        logger.info(f"HistoryPlotWidget initialized with history_window={history_window}s, "
                   f"poll_interval={poll_interval}s, plot_width={self.plot_width} chars, "
                   f"max_points={num_data_points}, plot_style={plot_style}")

    def update_history(self, history_data: list[tuple[float, float]]):
        """Update history data.

        Args:
            history_data: List of (timestamp, usage) tuples
        """
        data_points = len(history_data)
        if data_points > 0:
            time_span = history_data[-1][0] - history_data[0][0] if data_points >= 2 else 0
            logger.info(f"HistoryPlotWidget updated: {data_points} data points over {time_span:.1f}s")
        self.history_data = history_data
        self.refresh()

    def _create_braille_line_plot(self, usages: list[float], width: int, height: int) -> list[str]:
        """Create a high-resolution line graph using Braille patterns.

        Args:
            usages: List of usage percentages
            width: Plot width in characters
            height: Plot height in rows

        Returns:
            List of strings representing plot rows (top to bottom)
        """
        if not usages:
            return [" " * width] * height

        # Braille gives us 2x horizontal and 4x vertical resolution
        braille_width = width
        braille_height = height * 4  # Each character is 4 dots tall

        # Take only the last N points that fit in the plot (2 points per character)
        # Don't resample - use actual data points for constant width
        max_points = braille_width * 2
        data_to_plot = usages[-max_points:] if len(usages) > max_points else usages

        # Initialize empty braille grid
        braille_grid = [[0 for _ in range(braille_width)] for _ in range(height)]

        # Plot the line from right to left (newest on right)
        for i in range(len(data_to_plot)):
            # Calculate position from right to left
            # Start from the rightmost position and work backwards
            point_index = len(data_to_plot) - 1 - i
            x = braille_width - 1 - (i // 2)  # 2 columns per character, start from right
            col_offset = 1 - (i % 2)  # Right (1) then left (0) column within character

            # Convert usage to vertical position (0 = bottom, braille_height-1 = top)
            y_pos = int((data_to_plot[point_index] / 100.0) * (braille_height - 1))
            y_pos = braille_height - 1 - y_pos  # Flip for top-to-bottom

            # Calculate character row and dot row within character
            char_row = y_pos // 4
            dot_row = y_pos % 4

            if 0 <= char_row < height and 0 <= x < braille_width:
                # Set the appropriate dot
                braille_grid[char_row][x] |= self.BRAILLE_DOTS[dot_row][col_offset]

        # Convert braille grid to strings with color
        rows = []
        for row in braille_grid:
            row_str = ""
            for dots in row:
                char = chr(self.BRAILLE_BASE + dots)
                row_str += f"[cyan]{char}[/cyan]"
            rows.append(row_str)

        return rows

    def render(self) -> str:
        """Render the CPU history plot with enhanced visuals."""
        if not self.history_data or len(self.history_data) < 2:
            lines = []
            border_width = self.plot_width + 2  # +2 for padding around title
            lines.append("[dim]┌" + "─" * border_width + "┐[/dim]")
            for _ in range(6):
                lines.append("[dim]│[/dim]" + " " * border_width + "[dim]│[/dim]")
            lines.append("[dim]└" + "─" * border_width + "┘[/dim]")
            lines.append("[dim italic]  Collecting data... waiting for samples[/dim italic]")
            return "\n".join(lines)

        # Plot parameters
        plot_width = self.plot_width
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

        # Create braille line plot
        plot_rows = self._create_braille_line_plot(usages, plot_width, plot_height)

        # Build the complete plot with frame and Y-axis labels
        lines = []

        # Y-axis labels for each row
        y_labels = ["100%", " 80%", " 60%", " 40%", " 20%", "  0%"]

        # Top border with title
        title = " AVG CPU UTILIZATION "
        left_border = "─" * ((plot_width - len(title)) // 2)
        right_border = "─" * (plot_width - len(title) - len(left_border))
        lines.append(f"[dim]     ┌{left_border}[/dim][bold dodger_blue2]{title}[/bold dodger_blue2][dim]{right_border}┐[/dim]")

        # Plot rows with Y-axis
        for i, (label, row) in enumerate(zip(y_labels, plot_rows)):
            lines.append(f"[dim]{label} │[/dim]{row}[dim]│[/dim]")

        # Bottom border
        lines.append(f"[dim]     └{'─' * plot_width}┘[/dim]")

        # Window width label (centered)
        window_label = f"window width: {self.history_window}s"
        label_padding = (plot_width - len(window_label)) // 2
        lines.append(f"[dim]      {' ' * label_padding}{window_label}[/dim]")

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
        plot_style: str = "braille",
        poll_interval: float = 2.0,
        **kwargs,
    ):
        """Initialize server widget.

        Args:
            server_name: Name of the server
            low_threshold: Threshold for low usage
            medium_threshold: Threshold for medium usage
            start_collapsed: Whether to start in collapsed state
            history_window: Time window for history graph (seconds)
            plot_style: Visualization style for CPU history plot
            poll_interval: Polling interval in seconds
        """
        super().__init__(**kwargs)
        self.server_name = server_name
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.expanded = not start_collapsed
        self.history_window = history_window
        self.plot_style = plot_style
        self.poll_interval = poll_interval

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
        logger.info(f"ServerWidget initialized: name={server_name}, expanded={self.expanded}, thresholds=(low={low_threshold}%, med={medium_threshold}%), history_window={history_window}s")

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
                        self.history_widget = HistoryPlotWidget(
                            self.history_window,
                            self.plot_style,
                            self.low_threshold,
                            self.medium_threshold,
                            self.poll_interval
                        )
                        yield self.history_widget

    def on_mount(self):
        """Handle widget mount event."""
        logger.info(f"ServerWidget mounted: {self.server_name}")
        self.refresh_display()

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
                    core_widget = CPUCoreWidget(core, self.low_threshold, self.medium_threshold)
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
        if selected != self.is_selected:
            logger.info(f"ServerWidget '{self.server_name}' selection changed: {selected}")
        self.is_selected = selected
        self.refresh_display()

    def refresh_display(self):
        """Refresh the display of this widget."""
        if not self.header_widget:
            return

        # Animate spinner (increment for next refresh)
        self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)

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
        logger.info("StatusBar initialized")

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
        text-align: center;
    }

    HistoryPlotWidget {
        padding: 0 1;
        height: auto;
        text-align: center;
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
        logger.info(f"MonitoringApp initialized with {len(server_widgets)} server widgets")

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

    def _handle_delete_confirm(self, confirmed: bool) -> None:
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

            # Callback to main app to persist changes
            if self._on_delete_server:
                logger.info(f"Invoking delete callback for server '{server_name}'")
                self._on_delete_server(server_name)

            self.notify(f"Server '{server_name}' deleted", severity="information")
        elif not confirmed:
            logger.info("Server deletion was not confirmed by user")

    def action_add_server(self):
        """Add a new server."""
        logger.info("User action: add_server initiated, opening AddServerScreen")
        self.push_screen(AddServerScreen(), self._handle_add_server)

    def _handle_add_server(self, server_config: Optional[dict]) -> None:
        """Handle add server result."""
        if server_config:
            logger.info(f"Add server confirmed: {server_config['name']} ({server_config['host']})")
            # Callback to main app to create components and persist
            if self._on_add_server:
                logger.info(f"Invoking add callback for server '{server_config['name']}'")
                self._on_add_server(server_config)
            self.notify(f"Server '{server_config['name']}' added", severity="information")
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
