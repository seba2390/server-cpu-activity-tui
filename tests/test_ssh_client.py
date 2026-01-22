"""Tests for SSH client module."""

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from src.ssh_client import SSHClient, ServerConfig, ConnectionStatus


@pytest.fixture
def server_config():
    """Create a test server configuration."""
    return ServerConfig(
        name="test-server", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
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

    with patch("src.ssh_client.asyncssh.connect", new=mock_connect):
        with patch.object(Path, "exists", return_value=True):
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
    with patch("src.ssh_client.asyncssh.connect", side_effect=asyncio.TimeoutError()):
        with patch.object(Path, "exists", return_value=True):
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

    with patch("src.ssh_client.asyncssh.connect", new=mock_connect):
        with patch.object(Path, "exists", return_value=True):
            result = await ssh_client.ensure_connected()

            assert result is True
            assert ssh_client._connection is not None
