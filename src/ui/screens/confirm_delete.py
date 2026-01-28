"""Modal screen for confirming server deletion."""

import logging
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

logger = logging.getLogger(__name__)


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal screen for confirming server deletion."""

    CSS_PATH = Path(__file__).parent / "confirm_delete.tcss"

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, server_name: str, **kwargs: Any) -> None:
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
