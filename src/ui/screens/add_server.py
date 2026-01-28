"""Modal screen for adding a new server with arrow key navigation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option

from ..types import FieldDefinition
from ...validation import validate_hostname, validate_server_name, validate_username

if TYPE_CHECKING:
    from ...main import ServerConfigDict

logger = logging.getLogger(__name__)


class AddServerScreen(ModalScreen["ServerConfigDict | None"]):
    """Modal screen for adding a new server with arrow key navigation."""

    CSS_PATH = Path(__file__).parent / "add_server.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Submit"),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("enter", "enter_field", "Enter", show=False),
        Binding("right", "navigate_right", "Right", show=False),
        Binding("left", "navigate_left", "Left", show=False),
    ]

    # Class-level constant for label texts
    LABEL_TEXTS: dict[str, str] = {
        "label-name": "Server Name:",
        "label-host": "Host (IP or Hostname):",
        "label-username": "Username:",
        "label-authmethod": "Authentication Method:",
        "label-keypath": "SSH Key Path:",
        "label-password": "Password:",
    }

    # Class-level constant for field definitions
    FIELD_DEFINITIONS: list[FieldDefinition] = [
        {"id": "input-name", "label_id": "label-name", "type": "input"},
        {"id": "input-host", "label_id": "label-host", "type": "input"},
        {"id": "input-username", "label_id": "label-username", "type": "input"},
        {"id": "auth-method-list", "label_id": "label-authmethod", "type": "optionlist"},
        {"id": "input-keypath", "label_id": "label-keypath", "type": "input", "auth_type": "key"},
        {"id": "input-password", "label_id": "label-password", "type": "input", "auth_type": "password"},
        {"id": "add-btn", "label_id": None, "type": "button"},
        {"id": "cancel-btn", "label_id": None, "type": "button"},
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.auth_method = "key"  # Default authentication method
        self.fields: list[FieldDefinition] = []  # List of field definitions
        self.current_field_index = 0
        self.in_edit_mode = False
        logger.info("AddServerScreen initialized with two-level navigation")

    def compose(self) -> ComposeResult:
        with Vertical(id="add-dialog"):
            yield Label("Add New Server", id="add-title")

            with VerticalScroll(id="fields-scroll", can_focus=False):
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
                b1 = Button("Add Server", id="add-btn")
                b1.can_focus = False
                yield b1
                b2 = Button("Cancel", id="cancel-btn")
                b2.can_focus = False
                yield b2

    def on_mount(self) -> None:
        """Set up initial state when screen is mounted."""
        logger.info("AddServerScreen mounted, setting up initial state")

        # Cache widget references to avoid repeated query_one calls
        self._labels: dict[str, Label] = {
            "label-name": self.query_one("#label-name", Label),
            "label-host": self.query_one("#label-host", Label),
            "label-username": self.query_one("#label-username", Label),
            "label-authmethod": self.query_one("#label-authmethod", Label),
            "label-keypath": self.query_one("#label-keypath", Label),
            "label-password": self.query_one("#label-password", Label),
        }
        self._buttons: dict[str, Button] = {
            "add-btn": self.query_one("#add-btn", Button),
            "cancel-btn": self.query_one("#cancel-btn", Button),
        }
        self._inputs: dict[str, Input] = {
            "input-name": self.query_one("#input-name", Input),
            "input-host": self.query_one("#input-host", Input),
            "input-username": self.query_one("#input-username", Input),
            "input-keypath": self.query_one("#input-keypath", Input),
            "input-password": self.query_one("#input-password", Input),
        }
        self._auth_list: OptionList = self.query_one("#auth-method-list", OptionList)
        self._key_container = self.query_one("#key-container")
        self._password_container = self.query_one("#password-container")

        # Use class-level field definitions
        self.fields = list(self.FIELD_DEFINITIONS)

        # Select the first auth method (SSH Key) by default
        self._auth_list.highlighted = 0

        # Start in navigation mode, highlight first field
        self.current_field_index = 0
        self.in_edit_mode = False
        self._update_field_highlights()

        logger.info("Two-level navigation initialized - use ↑↓ to navigate, → or Enter to edit")

    def _update_field_highlights(self) -> None:
        """Update visual indicators to show which field is highlighted."""
        # Use cached references if available, fall back to query_one
        labels = getattr(self, "_labels", None)
        buttons = getattr(self, "_buttons", None)

        # Reset all labels to original text without arrows
        for label_id, text in self.LABEL_TEXTS.items():
            try:
                label = labels[label_id] if labels else self.query_one(f"#{label_id}", Label)
                label.update(text)
                label.remove_class("highlighted")
            except Exception as e:
                # Label might not exist yet during initial setup
                logger.info(f"Could not update label {label_id}: {e}")

        # Reset button highlights
        for btn_id in ["add-btn", "cancel-btn"]:
            try:
                btn = buttons[btn_id] if buttons else self.query_one(f"#{btn_id}", Button)
                btn.remove_class("highlighted-button")
            except Exception as e:
                # Button might not exist yet during initial setup
                logger.info(f"Could not update button {btn_id}: {e}")

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
        if field.get("label_id") and field["label_id"] in self.LABEL_TEXTS:
            label = labels[field["label_id"]] if labels else self.query_one(f"#{field['label_id']}", Label)
            label.add_class("highlighted")
            original_text = self.LABEL_TEXTS[field["label_id"]]

            # Update label text to include arrow
            if self.in_edit_mode:
                label.update(f"▶ {original_text}")
            else:
                label.update(f"→ {original_text}")

        # Highlight button if current field is a button
        if field["type"] == "button":
            try:
                btn = buttons[field["id"]] if buttons else self.query_one(f"#{field['id']}", Button)
                btn.add_class("highlighted-button")
            except Exception as e:
                logger.warning(f"Failed to highlight button {field['id']}: {e}")

        # Scroll to the highlighted field
        try:
            widget = self._get_field_widget(field["id"], field["type"])
            if field["type"] == "button" and hasattr(widget, "scroll_visible"):
                widget.scroll_visible(animate=False)
            else:
                # Get the field container (the Vertical holding the input)
                field_container = widget.parent
                if field_container and hasattr(field_container, "scroll_visible"):
                    field_container.scroll_visible(animate=False)
        except Exception as e:
            logger.warning(f"Failed to scroll to field {field['id']}: {e}")

        logger.info(f"Highlighted field {field['id']}, edit_mode={self.in_edit_mode}")

    def _get_field_widget(self, field_id: str, field_type: str) -> Input | OptionList | Button:
        """Get the cached widget for a field, or fall back to query_one.

        Args:
            field_id: The ID of the field widget
            field_type: The type of field ('input', 'optionlist', 'button')

        Returns:
            The widget for the field
        """
        if field_type == "input":
            inputs = getattr(self, "_inputs", None)
            if inputs and field_id in inputs:
                return inputs[field_id]
            return self.query_one(f"#{field_id}", Input)
        elif field_type == "optionlist":
            auth_list = getattr(self, "_auth_list", None)
            if auth_list:
                return auth_list
            return self.query_one(f"#{field_id}", OptionList)
        else:  # button
            buttons = getattr(self, "_buttons", None)
            if buttons and field_id in buttons:
                return buttons[field_id]
            return self.query_one(f"#{field_id}", Button)

    def _get_current_field(self) -> FieldDefinition | None:
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

        current_field = self._get_current_field()
        self._navigate_to_prev_valid_field()

        # If we were on cancel-btn and moved to add-btn, skip it (they are on same row)
        # We want to go to the field above the buttons
        new_field = self._get_current_field()
        if (current_field and current_field.get("id") == "cancel-btn" and
            new_field and new_field.get("id") == "add-btn"):
            self._navigate_to_prev_valid_field()

        logger.info(f"Navigated up to field index {self.current_field_index}")

    def action_navigate_down(self) -> None:
        """Navigate to next field (only in navigation mode)."""
        if self.in_edit_mode:
            return  # Arrow keys are for editing

        current_field = self._get_current_field()
        self._navigate_to_next_valid_field()

        # If we were on add-btn and moved to cancel-btn, skip it (they are on same row)
        # We want to go to the field below the buttons (or wrap to top)
        new_field = self._get_current_field()
        if (current_field and current_field.get("id") == "add-btn" and
            new_field and new_field.get("id") == "cancel-btn"):
            self._navigate_to_next_valid_field()

        logger.info(f"Navigated down to field index {self.current_field_index}")

    def action_navigate_right(self) -> None:
        """Handle Right arrow key."""
        field = self._get_current_field()
        if not field:
            return

        # Special handling for buttons
        if field.get("id") == "add-btn":
            # Move to cancel button
            # We know cancel button is next, so use navigate_next
            self._navigate_to_next_valid_field()
            return

        # If it's a button (e.g. cancel), do nothing (don't activate)
        if field["type"] == "button":
            return

        # Otherwise behave like Enter (enter field)
        self.action_enter_field()

    def action_navigate_left(self) -> None:
        """Handle Left arrow key."""
        # If in edit mode, exit edit mode
        if self.in_edit_mode:
            self.action_exit_field()
            return

        field = self._get_current_field()
        if not field:
            return

        # Special handling for buttons
        if field.get("id") == "cancel-btn":
            # Move to add button
            # We know add button is prev, so use navigate_prev
            self._navigate_to_prev_valid_field()
            return

    def action_enter_field(self) -> None:
        """Enter edit mode for current field (Enter key)."""
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
            widget = self._get_field_widget(field["id"], "input")
            widget.disabled = False
            widget.focus()
        elif field["type"] == "optionlist":
            widget = self._get_field_widget(field["id"], "optionlist")
            widget.disabled = False
            widget.focus()
        elif field["type"] == "button":
            # Buttons are activated immediately
            self.in_edit_mode = False
            button = self._get_field_widget(field["id"], "button")
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
            widget = self._get_field_widget(field["id"], "input")
            widget.disabled = True
            widget.blur()
            # Return focus to the screen
            self.focus()
        elif field["type"] == "optionlist":
            widget = self._get_field_widget(field["id"], "optionlist")
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
            logger.info("Auth method selected, moved to next field")

    def _update_auth_fields(self) -> None:
        """Show/hide authentication fields based on selected method."""
        # Use cached references if available
        key_container = getattr(self, "_key_container", None) or self.query_one("#key-container")
        password_container = getattr(self, "_password_container", None) or self.query_one("#password-container")

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

        # Validate server name
        name_validation = validate_server_name(name)
        if not name_validation.valid:
            logger.warning(f"Add server form submission failed: {name_validation.error_message}")
            self.notify(name_validation.error_message or "Invalid server name", severity="error")
            self.query_one("#input-name", Input).focus()
            return

        if not host:
            logger.warning("Add server form submission failed: missing host")
            self.notify("Host (IP or hostname) is required", severity="error")
            self.query_one("#input-host", Input).focus()
            return

        # Validate hostname/IP
        host_validation = validate_hostname(host)
        if not host_validation.valid:
            logger.warning(f"Add server form submission failed: {host_validation.error_message}")
            self.notify(host_validation.error_message or "Invalid host", severity="error")
            self.query_one("#input-host", Input).focus()
            return

        if not username:
            logger.warning("Add server form submission failed: missing username")
            self.notify("Username is required", severity="error")
            self.query_one("#input-username", Input).focus()
            return

        # Validate username
        username_validation = validate_username(username)
        if not username_validation.valid:
            logger.warning(f"Add server form submission failed: {username_validation.error_message}")
            self.notify(username_validation.error_message or "Invalid username", severity="error")
            self.query_one("#input-username", Input).focus()
            return

        # Build server config with auth_method
        server_config_dict: dict[str, str | None] = {
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

            server_config_dict["key_path"] = key_path
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
            server_config_dict["_password"] = password  # Temporary key for in-memory use

        # Type is already validated above
        server_config = server_config_dict  # type: ignore[assignment]

        logger.info(f"Server configuration validated successfully: {name}")

        self.notify(f"Adding server '{name}'...", severity="information")
        self.dismiss(server_config)
