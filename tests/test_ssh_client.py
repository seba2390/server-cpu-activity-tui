"""Tests for SSH client module."""

import stat
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.ssh_client import ConnectionStatus, ServerConfig, SSHClient


def create_mock_stat(mode: int = 0o600):
    """Create a mock stat result with specific mode."""
    mock_stat = MagicMock()
    # Create a mode that passes permission checks (no group/others access)
    mock_stat.st_mode = stat.S_IFREG | mode
    return mock_stat


@pytest.fixture
def server_config():
    """Create a test server configuration."""
    return ServerConfig(
        name="test-server",
        host="192.168.1.100",
        username="testuser",
        auth_method="key",
        key_path="/tmp/test_key.pem"
    )


@pytest.fixture
def ssh_client(server_config):
    """Create an SSH client instance."""
    return SSHClient(config=server_config, connection_timeout=5, max_retries=2, retry_delay=1)


@pytest.mark.asyncio
async def test_ssh_client_initialization(ssh_client, server_config):
    """Test SSH client initialization."""
    assert ssh_client.config == server_config
    assert ssh_client.connection_timeout == 5
    assert ssh_client.max_retries == 2
    assert ssh_client.retry_delay == 1
    assert not ssh_client.status.connected


@pytest.mark.asyncio
async def test_connect_success(ssh_client):
    """Test successful SSH connection."""
    # Mock the connection
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)

    async def mock_connect(*args, **kwargs):
        return mock_connection

    # Create a mock Path that handles the chaining: Path(...).expanduser()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stat.return_value = create_mock_stat(0o600)
    mock_path_instance.__str__ = lambda self: "/tmp/test_key.pem"
    # The Path(...) constructor returns something, then .expanduser() is called on it
    # Both should return the same mock path instance
    mock_path_instance.expanduser.return_value = mock_path_instance

    with (
        patch("src.ssh_client.asyncssh.connect", new=mock_connect),
        patch("src.ssh_client.Path", return_value=mock_path_instance),
    ):
        result = await ssh_client.connect()

        assert result is True
        assert ssh_client.status.connected
        assert ssh_client._connection is not None


@pytest.mark.asyncio
async def test_connect_key_not_found(ssh_client):
    """Test connection failure when SSH key doesn't exist."""
    with patch.object(Path, "exists", return_value=False):
        result = await ssh_client.connect()

        assert result is False
        assert not ssh_client.status.connected
        assert "SSH key not found" in ssh_client.status.error_message


@pytest.mark.asyncio
async def test_connect_timeout(ssh_client):
    """Test connection timeout."""
    # Create a mock Path that handles the chaining: Path(...).expanduser()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stat.return_value = create_mock_stat(0o600)
    mock_path_instance.__str__ = lambda self: "/tmp/test_key.pem"
    mock_path_instance.expanduser.return_value = mock_path_instance

    with (
        patch("src.ssh_client.asyncssh.connect", side_effect=TimeoutError()),
        patch("src.ssh_client.Path", return_value=mock_path_instance),
    ):
        result = await ssh_client.connect()

        assert result is False
        assert not ssh_client.status.connected
        assert "timeout" in ssh_client.status.error_message.lower()


@pytest.mark.asyncio
async def test_disconnect(ssh_client):
    """Test SSH disconnection."""
    # Setup a mock connection
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)
    mock_connection.close = Mock()
    mock_connection.wait_closed = AsyncMock()
    ssh_client._connection = mock_connection
    ssh_client.status = ConnectionStatus(connected=True)

    await ssh_client.disconnect()

    assert ssh_client._connection is None
    assert not ssh_client.status.connected
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_command_success(ssh_client):
    """Test successful command execution."""
    # Setup mock connection and result
    mock_result = Mock()
    mock_result.stdout = "test output\n"

    mock_connection = AsyncMock()
    mock_connection.run = AsyncMock(return_value=mock_result)
    mock_connection.is_closed.return_value = False

    ssh_client._connection = mock_connection

    result = await ssh_client.execute_command("echo test")

    assert result == "test output"
    mock_connection.run.assert_called_once_with("echo test", check=True)


@pytest.mark.asyncio
async def test_execute_command_not_connected(ssh_client):
    """Test command execution when not connected."""
    result = await ssh_client.execute_command("echo test")

    assert result is None


@pytest.mark.asyncio
async def test_is_connected(ssh_client):
    """Test connection status check."""
    # Not connected
    assert await ssh_client.is_connected() is False

    # Connected
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)
    ssh_client._connection = mock_connection

    assert await ssh_client.is_connected() is True

    # Connection closed
    mock_connection.is_closed = Mock(return_value=True)
    assert await ssh_client.is_connected() is False


@pytest.mark.asyncio
async def test_ensure_connected_already_connected(ssh_client):
    """Test ensure_connected when already connected."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)
    ssh_client._connection = mock_connection

    result = await ssh_client.ensure_connected()

    assert result is True


@pytest.mark.asyncio
async def test_ensure_connected_reconnect(ssh_client):
    """Test ensure_connected performs reconnection."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)

    async def mock_connect(*args, **kwargs):
        return mock_connection

    # Create a mock Path that returns True for exists() and proper stat()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stat.return_value = create_mock_stat(0o600)
    mock_path_instance.__str__ = lambda self: "/tmp/test_key.pem"
    mock_path_instance.expanduser.return_value = mock_path_instance

    with (
        patch("src.ssh_client.asyncssh.connect", new=mock_connect),
        patch("src.ssh_client.Path", return_value=mock_path_instance),
    ):
        result = await ssh_client.ensure_connected()

        assert result is True
        assert ssh_client._connection is not None


@pytest.mark.asyncio
async def test_connect_retry_logic(ssh_client):
    """Test connection retry logic on failures."""
    # Create a mock Path that handles the chaining: Path(...).expanduser()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stat.return_value = create_mock_stat(0o600)
    mock_path_instance.__str__ = lambda self: "/tmp/test_key.pem"
    mock_path_instance.expanduser.return_value = mock_path_instance

    with patch("src.ssh_client.Path", return_value=mock_path_instance):
        # Simulate 2 failures then success
        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)

        call_count = 0

        async def mock_connect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("Connection refused")
            return mock_conn

        with patch("src.ssh_client.asyncssh.connect", new=mock_connect):
            result = await ssh_client.connect()

            assert result is True
            assert call_count == 2


@pytest.mark.asyncio
async def test_connect_exhausted_retries(ssh_client):
    """Test connection when all retries are exhausted."""
    # Create a mock Path that handles the chaining: Path(...).expanduser()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stat.return_value = create_mock_stat(0o600)
    mock_path_instance.__str__ = lambda self: "/tmp/test_key.pem"
    mock_path_instance.expanduser.return_value = mock_path_instance

    with (
        patch("src.ssh_client.Path", return_value=mock_path_instance),
        patch("src.ssh_client.asyncssh.connect", side_effect=OSError("Connection refused")),
    ):
        result = await ssh_client.connect()

        assert result is False
        assert not ssh_client.status.connected


@pytest.mark.asyncio
async def test_disconnect_when_not_connected(ssh_client):
    """Test disconnecting when not connected."""
    assert ssh_client._connection is None

    # Should handle gracefully
    await ssh_client.disconnect()

    assert ssh_client._connection is None


@pytest.mark.asyncio
async def test_execute_command_ssh_error(ssh_client):
    """Test command execution with SSH error."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)

    # Simulate SSH error
    from asyncssh import Error

    mock_connection.run = AsyncMock(side_effect=Error("test",  reason="Connection lost"))

    ssh_client._connection = mock_connection

    result = await ssh_client.execute_command("echo test")

    assert result is None
    # Connection should be marked as disconnected
    assert ssh_client._connection is None
    assert not ssh_client.status.connected


@pytest.mark.asyncio
async def test_execute_command_strips_output(ssh_client):
    """Test command execution strips whitespace from output."""
    mock_result = Mock()
    mock_result.stdout = "  test output  \n\n"

    mock_connection = AsyncMock()
    mock_connection.run = AsyncMock(return_value=mock_result)
    mock_connection.is_closed = Mock(return_value=False)

    ssh_client._connection = mock_connection

    result = await ssh_client.execute_command("echo test")

    assert result == "test output"


@pytest.mark.asyncio
async def test_is_connected_with_closed_connection(ssh_client):
    """Test is_connected with a closed connection."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=True)

    ssh_client._connection = mock_connection

    assert await ssh_client.is_connected() is False


@pytest.mark.asyncio
async def test_ensure_connected_when_reconnect_fails(ssh_client):
    """Test ensure_connected when reconnection fails."""
    # Connection is None, so it will try to reconnect
    ssh_client._connection = None

    with patch.object(ssh_client, "connect", return_value=False):
        result = await ssh_client.ensure_connected()

        assert result is False


@pytest.mark.asyncio
async def test_connect_already_connected(ssh_client):
    """Test connecting when already connected."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = Mock(return_value=False)

    ssh_client._connection = mock_connection

    result = await ssh_client.connect()

    # Should return True immediately without creating new connection
    assert result is True
    assert ssh_client._connection == mock_connection
