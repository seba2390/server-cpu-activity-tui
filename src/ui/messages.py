"""Messages for UI event communication."""

from textual.message import Message

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import ServerConfigDict


class ServerDeleted(Message):
    """Message posted when a server is deleted from the UI.

    Attributes:
        server_name: The name of the deleted server.
    """

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        super().__init__()


class ServerAdded(Message):
    """Message posted when a new server is added via the UI.

    Attributes:
        server_config: The configuration dictionary for the new server.
    """

    def __init__(self, server_config: "ServerConfigDict") -> None:
        self.server_config = server_config
        super().__init__()
