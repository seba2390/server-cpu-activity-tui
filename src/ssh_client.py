"""SSH client for remote server connections and command execution."""

import asyncio
import logging
import stat
from dataclasses import dataclass
from pathlib import Path

import asyncssh


logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for a remote server."""

    name: str
    host: str
    username: str
    auth_method: str = "key"  # "key" or "password"
    key_path: str | None = None
    password: str | None = None
    verify_host_key: bool = True  # Host key verification enabled by default for security

    def __post_init__(self):
        """Validate authentication configuration."""
        if self.auth_method not in ["key", "password"]:
            raise ValueError("auth_method must be 'key' or 'password'")

        if self.auth_method == "key" and not self.key_path:
            raise ValueError("key_path is required when auth_method is 'key'")

        # Password will be set later if auth_method is "password"


@dataclass
class ConnectionStatus:
    """Status of an SSH connection."""

    connected: bool
    error_message: str | None = None
    last_attempt: float | None = None


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

        self._connection: asyncssh.SSHClientConnection | None = None
        self._lock = asyncio.Lock()
        self.status = ConnectionStatus(connected=False)

        logger.info(f"SSHClient initialized for '{config.name}' ({config.host}): "
                   f"timeout={connection_timeout}s, max_retries={max_retries}, retry_delay={retry_delay}s")

    async def connect(self) -> bool:
        """Establish SSH connection to the server.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._lock:
            if self._connection is not None:
                logger.info(f"{self.config.name}: Already connected, skipping connection attempt")
                return True

            # Determine authentication method
            auth_display = self.config.auth_method
            logger.info(f"{self.config.name}: Preparing to connect - host={self.config.host}, user={self.config.username}, auth={auth_display}")

            # Prepare connection kwargs based on authentication method
            connect_kwargs = {
                "host": self.config.host,
                "username": self.config.username,
                "known_hosts": None if not self.config.verify_host_key else (),  # Use default known_hosts if enabled
            }

            if self.config.auth_method == "password":
                # Password-based authentication
                if not self.config.password:
                    error_msg = "Password not provided for password authentication"
                    logger.error(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)
                    return False
                connect_kwargs["password"] = self.config.password
                logger.info(f"{self.config.name}: Using password authentication")
            else:
                # Key-based authentication
                if not self.config.key_path:
                    error_msg = "SSH key path not provided for key authentication"
                    logger.error(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)
                    return False

                key_path = Path(self.config.key_path).expanduser()

                # Validate key file exists
                if not key_path.exists():
                    error_msg = f"SSH key not found: {key_path}"
                    logger.error(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)
                    return False

                # Validate key file permissions (should be 600 or 400 for security)
                try:
                    key_stat = key_path.stat()
                    key_perms = stat.filemode(key_stat.st_mode)
                    octal_perms = oct(key_stat.st_mode)[-3:]

                    # Check if permissions are too open (not 600, 400, or stricter)
                    if key_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):  # Group or others have any permissions
                        error_msg = (
                            f"SSH key has insecure permissions: {key_perms} ({octal_perms}). "
                            f"Key file should be readable only by owner (chmod 600 {key_path})"
                        )
                        logger.error(f"{self.config.name}: {error_msg}")
                        self.status = ConnectionStatus(connected=False, error_message=error_msg)
                        return False

                    logger.info(f"{self.config.name}: SSH key verified at: {key_path} (permissions: {octal_perms})")
                except OSError as e:
                    error_msg = f"Failed to check SSH key permissions: {e}"
                    logger.error(f"{self.config.name}: {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)
                    return False

                connect_kwargs["client_keys"] = [str(key_path)]

            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"{self.config.name}: Connection attempt {attempt + 1}/{self.max_retries} to {self.config.host}"
                    )

                    self._connection = await asyncio.wait_for(
                        asyncssh.connect(**connect_kwargs),
                        timeout=self.connection_timeout,
                    )

                    logger.info(f"{self.config.name}: Successfully connected to {self.config.host} on attempt {attempt + 1}")
                    self.status = ConnectionStatus(connected=True)
                    return True

                except TimeoutError:
                    error_msg = f"Connection timeout after {self.connection_timeout}s"
                    logger.warning(f"{self.config.name}: Attempt {attempt + 1}/{self.max_retries} - {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)

                except (asyncssh.Error, OSError) as e:
                    error_msg = f"Connection failed: {e!s}"
                    logger.warning(f"{self.config.name}: Attempt {attempt + 1}/{self.max_retries} - {error_msg}")
                    self.status = ConnectionStatus(connected=False, error_message=error_msg)

                if attempt < self.max_retries - 1:
                    logger.info(f"{self.config.name}: Waiting {self.retry_delay}s before retry...")
                    await asyncio.sleep(self.retry_delay)

            logger.error(f"{self.config.name}: Failed to connect after {self.max_retries} attempts")
            return False

    async def disconnect(self):
        """Close the SSH connection."""
        async with self._lock:
            if self._connection is not None:
                logger.info(f"{self.config.name}: Disconnecting from {self.config.host}...")
                self._connection.close()
                await self._connection.wait_closed()
                self._connection = None
                self.status = ConnectionStatus(connected=False)
                logger.info(f"{self.config.name}: Disconnected successfully")
            else:
                logger.info(f"{self.config.name}: Already disconnected, no action needed")

    async def execute_command(self, command: str) -> str | None:
        """Execute a command on the remote server.

        Args:
            command: Command to execute

        Returns:
            Command output as string, or None if execution failed
        """
        async with self._lock:
            if self._connection is None:
                logger.error(f"{self.config.name}: Cannot execute command - not connected")
                return None

            # Truncate command for logging if too long
            cmd_display = command if len(command) <= 50 else command[:47] + "..."
            logger.info(f"{self.config.name}: Executing command: {cmd_display}")

            try:
                result = await self._connection.run(command, check=True)
                if result.stdout:
                    output_length = len(result.stdout)
                    logger.info(f"{self.config.name}: Command executed successfully, output length: {output_length} bytes")
                    # Ensure output is string and strip
                    output = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8")
                    return output.strip()
                return None

            except asyncssh.ProcessError as e:
                stderr = e.stderr or ""
                stderr_preview = stderr[:100] if len(stderr) <= 100 else stderr[:97] + "..."
                logger.error(f"{self.config.name}: Command failed: {cmd_display} - stderr: {stderr_preview}")
                return None

            except asyncssh.Error as e:
                logger.error(f"{self.config.name}: SSH error during command execution: {e}")
                # Connection might be broken, mark as disconnected
                logger.warning(f"{self.config.name}: Marking connection as lost due to SSH error")
                self._connection = None
                self.status = ConnectionStatus(connected=False, error_message="Connection lost")
                return None

    async def is_connected(self) -> bool:
        """Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        async with self._lock:
            is_conn = self._connection is not None and not self._connection.is_closed()
            if not is_conn and self._connection is not None:
                logger.warning(f"{self.config.name}: Connection object exists but is closed")
            return is_conn

    async def ensure_connected(self) -> bool:
        """Ensure connection is active, reconnecting if necessary.

        Returns:
            True if connected, False otherwise
        """
        # Use lock to prevent race condition during reconnection
        async with self._lock:
            # Check if already connected
            is_conn = self._connection is not None and not self._connection.is_closed()
            if is_conn:
                return True

            # Need to reconnect - release lock temporarily to allow connect() to acquire it
            logger.info(f"{self.config.name}: Connection not active, attempting to reconnect...")

        # Reconnect outside the lock
        result = await self.connect()
        if result:
            logger.info(f"{self.config.name}: Reconnection successful")
        else:
            logger.warning(f"{self.config.name}: Reconnection failed")
        return result
