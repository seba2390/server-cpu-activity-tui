"""SSH client for remote server connections and command execution."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asyncssh

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for a remote server."""

    name: str
    host: str
    username: str
    key_path: str


@dataclass
class ConnectionStatus:
    """Status of an SSH connection."""

    connected: bool
    error_message: Optional[str] = None
    last_attempt: Optional[float] = None


class SSHClient:
    """Manages SSH connections to remote servers."""

    def __init__(
        self,
        config: ServerConfig,
        connection_timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 5,
    ):
        """Initialize SSH client.

        Args:
            config: Server configuration
            connection_timeout: Connection timeout in seconds
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay between retry attempts in seconds
        """
        self.config = config
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._connection: Optional[asyncssh.SSHClientConnection] = None
        self._lock = asyncio.Lock()
        self.status = ConnectionStatus(connected=False)

    async def connect(self) -> bool:
        """Establish SSH connection to the server.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._lock:
            if self._connection is not None:
                return True

            key_path = Path(self.config.key_path).expanduser()

            if not key_path.exists():
                error_msg = f"SSH key not found: {key_path}"
                logger.error(f"{self.config.name}: {error_msg}")
                self.status = ConnectionStatus(connected=False, error_message=error_msg)
                return False

            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"{self.config.name}: Connecting to {self.config.host} "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )

                    self._connection = await asyncio.wait_for(
                        asyncssh.connect(
                            self.config.host,
                            username=self.config.username,
                            client_keys=[str(key_path)],
                            known_hosts=None,  # Disable host key checking for simplicity
                        ),
                        timeout=self.connection_timeout,
                    )

                    logger.info(f"{self.config.name}: Connected successfully")
                    self.status = ConnectionStatus(connected=True)
                    return True

                except asyncio.TimeoutError:
                    error_msg = f"Connection timeout after {self.connection_timeout}s"
                    logger.warning(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)

                except (asyncssh.Error, OSError) as e:
                    error_msg = f"Connection failed: {str(e)}"
                    logger.warning(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)

                if attempt < self.max_retries - 1:
                    logger.info(f"{self.config.name}: Retrying in {self.retry_delay}s...")
                    await asyncio.sleep(self.retry_delay)

            logger.error(f"{self.config.name}: Failed to connect after {self.max_retries} attempts")
            return False

    async def disconnect(self):
        """Close the SSH connection."""
        async with self._lock:
            if self._connection is not None:
                self._connection.close()
                await self._connection.wait_closed()
                self._connection = None
                self.status = ConnectionStatus(connected=False)
                logger.info(f"{self.config.name}: Disconnected")

    async def execute_command(self, command: str) -> Optional[str]:
        """Execute a command on the remote server.

        Args:
            command: Command to execute

        Returns:
            Command output as string, or None if execution failed
        """
        async with self._lock:
            if self._connection is None:
                logger.error(f"{self.config.name}: Not connected")
                return None

            try:
                result = await self._connection.run(command, check=True)
                return result.stdout.strip()

            except asyncssh.ProcessError as e:
                logger.error(f"{self.config.name}: Command failed: {command} - {e.stderr}")
                return None

            except asyncssh.Error as e:
                logger.error(f"{self.config.name}: SSH error during command execution: {e}")
                # Connection might be broken, mark as disconnected
                self._connection = None
                self.status = ConnectionStatus(connected=False, error_message="Connection lost")
                return None

    async def is_connected(self) -> bool:
        """Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        async with self._lock:
            return self._connection is not None and not self._connection.is_closed()

    async def ensure_connected(self) -> bool:
        """Ensure connection is active, reconnecting if necessary.

        Returns:
            True if connected, False otherwise
        """
        if await self.is_connected():
            return True

        return await self.connect()
