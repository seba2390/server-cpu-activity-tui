"""Integration tests for the CPU monitoring application."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.main import CPUMonitoringApp
from src.monitor import CPUMonitor
from src.ssh_client import ServerConfig, SSHClient


class TestIntegration:
    """Integration tests for the full application."""

    @pytest.mark.asyncio
    async def test_full_app_lifecycle(self, tmp_path):
        """Test the full application lifecycle: initialize -> start -> stop."""
        # Create a temporary config file
        config_file = tmp_path / "test_config.yaml"
        config_content = """
servers:
  - name: "Test Server"
    host: "localhost"
    username: "testuser"
    auth_method: key
    key_path: "~/.ssh/test_key"
    verify_host_key: false

monitoring:
  poll_interval: 0.1
  ui_refresh_interval: 0.1
  history_window: 10

display:
  plot_style: "braille"
"""
        config_file.write_text(config_content)

        # Create app instance
        app = CPUMonitoringApp(config_path=str(config_file))
        app.load_config()

        # Verify config loaded correctly
        assert len(app.config["servers"]) == 1
        assert app.config["servers"][0]["name"] == "Test Server"

        # Initialize components
        with patch("getpass.getpass", return_value="test_password"):
            app.initialize_components()

        # Verify components created
        assert len(app.ssh_clients) == 1
        assert len(app.monitors) == 1
        assert len(app.server_widgets) == 1

        # Test monitoring start/stop without UI
        with patch.object(app.ssh_clients[0], "connect", new_callable=AsyncMock, return_value=False):
            await app.start_monitoring()

            # Wait a bit for monitoring to run
            await asyncio.sleep(0.3)

            # Stop monitoring
            await app.stop_monitoring()

        # Verify cleanup
        assert not app._running

    @pytest.mark.asyncio
    async def test_add_server_integration(self, tmp_path):
        """Test adding a new server to a running configuration."""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
servers:
  - name: "Server 1"
    host: "192.168.1.1"
    username: "user1"
    auth_method: key
    key_path: "~/.ssh/key1"
    verify_host_key: false

monitoring:
  poll_interval: 0.1
"""
        config_file.write_text(config_content)

        app = CPUMonitoringApp(config_path=str(config_file))
        app.load_config()

        with patch("getpass.getpass", return_value="test_password"):
            app.initialize_components()

        initial_count = len(app.ssh_clients)

        # Add a new server
        new_server_config = {
            "name": "Server 2",
            "host": "192.168.1.2",
            "username": "user2",
            "auth_method": "key",
            "key_path": "~/.ssh/key2",
            "verify_host_key": False,
        }

        app.add_server(new_server_config)

        # Verify server was added
        assert len(app.ssh_clients) == initial_count + 1
        assert len(app.monitors) == initial_count + 1
        assert len(app.server_widgets) == initial_count + 1
        assert len(app.config["servers"]) == initial_count + 1

        # Cleanup
        await app.stop_monitoring()

    @pytest.mark.asyncio
    async def test_delete_server_integration(self, tmp_path):
        """Test deleting a server from a running configuration."""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
servers:
  - name: "Server 1"
    host: "192.168.1.1"
    username: "user1"
    auth_method: key
    key_path: "~/.ssh/key1"
    verify_host_key: false
  - name: "Server 2"
    host: "192.168.1.2"
    username: "user2"
    auth_method: key
    key_path: "~/.ssh/key2"
    verify_host_key: false

monitoring:
  poll_interval: 0.1
"""
        config_file.write_text(config_content)

        app = CPUMonitoringApp(config_path=str(config_file))
        app.load_config()

        with patch("getpass.getpass", return_value="test_password"):
            app.initialize_components()

        initial_count = len(app.ssh_clients)

        # Start monitoring
        with patch.object(SSHClient, "connect", new_callable=AsyncMock, return_value=False):
            await app.start_monitoring()

        # Delete a server
        app.delete_server("Server 1")

        # Verify server was deleted
        assert len(app.ssh_clients) == initial_count - 1
        assert len(app.monitors) == initial_count - 1
        assert len(app.server_widgets) == initial_count - 1
        assert len(app.config["servers"]) == initial_count - 1

        # Wait for cleanup tasks to complete
        await asyncio.sleep(0.2)

        # Cleanup
        await app.stop_monitoring()

    @pytest.mark.asyncio
    async def test_consecutive_failures_handling(self):
        """Test that consecutive failures are properly tracked and handled."""
        config = ServerConfig(
            name="test_server",
            host="localhost",
            username="testuser",
            auth_method="key",
            key_path="~/.ssh/test_key",
            verify_host_key=False,
        )

        ssh_client = SSHClient(config=config, connection_timeout=0.1, max_retries=1, retry_delay=0.1)
        monitor = CPUMonitor(ssh_client=ssh_client, poll_interval=0.05, history_window=10)

        # Mock ensure_connected to always fail and set error status
        async def mock_ensure_connected():
            ssh_client.status.error_message = "Connection failed"
            return False

        with patch.object(ssh_client, "ensure_connected", new=mock_ensure_connected):
            await monitor.start()

            # Wait for max_consecutive_failures iterations
            # max_consecutive_failures = 10, poll_interval = 0.05
            # Should stop after ~0.5 seconds
            await asyncio.sleep(1.0)

            # Monitor should have stopped itself due to consecutive failures
            metrics = await monitor.get_metrics()

            # Verify we got disconnected metrics
            assert metrics is not None
            assert not metrics.connected
            # Error message should be present from SSH client status
            assert metrics.error_message is not None

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_cleanup_tasks_completion(self, tmp_path):
        """Test that cleanup tasks complete properly before shutdown."""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
servers:
  - name: "Server 1"
    host: "192.168.1.1"
    username: "user1"
    auth_method: key
    key_path: "~/.ssh/key1"
    verify_host_key: false

monitoring:
  poll_interval: 0.1
"""
        config_file.write_text(config_content)

        app = CPUMonitoringApp(config_path=str(config_file))
        app.load_config()

        with patch("getpass.getpass", return_value="test_password"):
            app.initialize_components()

        # Mock SSH connect to avoid actual connection
        with patch.object(SSHClient, "connect", new_callable=AsyncMock, return_value=False):
            await app.start_monitoring()

        # Delete server (creates cleanup task)
        app.delete_server("Server 1")

        # Verify cleanup task was created
        assert len(app._cleanup_tasks) > 0

        # Stop monitoring (should wait for cleanup tasks)
        await app.stop_monitoring()

        # Verify cleanup tasks were completed and cleared
        assert len(app._cleanup_tasks) == 0

    @pytest.mark.asyncio
    async def test_config_plot_style_respected(self, tmp_path):
        """Test that plot_style from config is properly used."""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
servers:
  - name: "Server 1"
    host: "192.168.1.1"
    username: "user1"
    auth_method: key
    key_path: "~/.ssh/key1"
    verify_host_key: false

display:
  plot_style: "block"
"""
        config_file.write_text(config_content)

        app = CPUMonitoringApp(config_path=str(config_file))
        app.load_config()

        with patch("getpass.getpass", return_value="test_password"):
            app.initialize_components()

        # Verify plot_style was used from config
        widget = app.server_widgets[0]
        assert widget.plot_style == "block"

        await app.stop_monitoring()

    @pytest.mark.asyncio
    async def test_host_key_verification_default(self):
        """Test that host key verification is enabled by default."""
        config = ServerConfig(
            name="test_server",
            host="localhost",
            username="testuser",
            auth_method="key",
            key_path="~/.ssh/test_key",
            # Not specifying verify_host_key - should default to True
        )

        # Verify default is True
        assert config.verify_host_key is True
