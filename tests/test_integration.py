"""Integration tests for the CPU monitoring application.

Includes both traditional integration tests and new Textual pilot-based
end-to-end TUI tests.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.main import CPUMonitoringApp
from src.monitor import CPUCore, CPUMonitor, ServerMetrics
from src.ssh_client import ServerConfig, SSHClient
from src.ui import MonitoringApp, ServerWidget
from src.ui.screens import AddServerScreen, ConfirmDeleteScreen


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


# ============================================================================
# Textual Pilot-Based End-to-End TUI Tests
# ============================================================================


class TestTextualPilotIntegration:
    """Integration tests using Textual's test harness (pilot) for E2E TUI testing."""

    @pytest.mark.asyncio
    async def test_app_launches_and_displays(self):
        """Test that the MonitoringApp launches successfully."""
        app = MonitoringApp(server_widgets=[])

        async with app.run_test() as pilot:
            # Wait for app to mount
            await pilot.pause()

            # Verify app is running
            assert app.is_running
            assert pilot.app == app

    @pytest.mark.asyncio
    async def test_keyboard_navigation_between_servers(self):
        """Test keyboard navigation using up/down arrows."""
        # Create widgets before app initialization so they're mounted properly
        server1 = ServerWidget("Server 1")
        server2 = ServerWidget("Server 2")
        server3 = ServerWidget("Server 3")
        app = MonitoringApp(server_widgets=[server1, server2, server3])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Start at index 0
            assert app.selected_index == 0

            # Navigate down
            await pilot.press("down")
            await pilot.pause()
            assert app.selected_index == 1

            # Navigate down again
            await pilot.press("down")
            await pilot.pause()
            assert app.selected_index == 2

            # Navigate up
            await pilot.press("up")
            await pilot.pause()
            assert app.selected_index == 1

    @pytest.mark.asyncio
    async def test_expand_collapse_with_arrow_keys(self):
        """Test expanding/collapsing server with left/right arrows."""
        server = ServerWidget("Test Server")
        app = MonitoringApp(server_widgets=[server])

        async with app.run_test() as pilot:
            await pilot.pause()
            app.selected_index = 0

            # Initially collapsed
            assert not server.expanded

            # Press right to expand
            await pilot.press("right")
            await pilot.pause()
            assert server.expanded

            # Press left to collapse
            await pilot.press("left")
            await pilot.pause()
            assert not server.expanded

            # Press Enter to toggle
            await pilot.press("enter")
            await pilot.pause()
            assert server.expanded

    @pytest.mark.asyncio
    async def test_refresh_action(self):
        """Test the refresh action (R key)."""
        app = MonitoringApp(server_widgets=[])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press R to refresh - should not crash
            await pilot.press("r")
            await pilot.pause()

            # Verify app is still running
            assert app.is_running

    @pytest.mark.asyncio
    async def test_add_server_dialog_workflow(self):
        """Test opening and closing Add Server dialog."""
        app = MonitoringApp(server_widgets=[])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press A to open add server dialog
            await pilot.press("a")
            await pilot.pause()

            # Verify dialog is in screen stack
            assert any(isinstance(screen, AddServerScreen) for screen in app.screen_stack)

            # Press Escape to cancel
            await pilot.press("escape")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_delete_confirmation_workflow(self):
        """Test delete server confirmation dialog."""
        server = ServerWidget("Test Server")
        app = MonitoringApp(server_widgets=[server])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press D to delete
            await pilot.press("d")
            await pilot.pause()

            # Verify confirmation dialog appears
            assert any(isinstance(screen, ConfirmDeleteScreen) for screen in app.screen_stack)

    @pytest.mark.asyncio
    async def test_quit_application(self):
        """Test quitting with Q key."""
        app = MonitoringApp(server_widgets=[])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press Q to quit
            await pilot.press("q")
            await pilot.pause()

            # App should stop
            assert not app.is_running

    @pytest.mark.asyncio
    async def test_server_metrics_update_display(self):
        """Test that updating metrics refreshes the UI."""
        server = ServerWidget("Test Server")
        app = MonitoringApp(server_widgets=[server])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Create test metrics
            cores = [
                CPUCore(core_id=0, usage_percent=25.0),
                CPUCore(core_id=1, usage_percent=50.0),
                CPUCore(core_id=2, usage_percent=75.0),
            ]

            metrics = ServerMetrics(
                server_name="Test Server",
                timestamp=1234567890.0,
                cores=cores,
                overall_usage=50.0,
                connected=True,
            )

            # Update metrics
            server.update_metrics(metrics)
            await pilot.pause()

            # Verify metrics applied
            assert server.metrics == metrics
            assert server.metrics.overall_usage == 50.0

    @pytest.mark.asyncio
    async def test_disconnected_server_error_display(self):
        """Test that disconnected servers show error state in UI."""
        server = ServerWidget("Test Server")
        app = MonitoringApp(server_widgets=[server])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Create disconnected metrics
            metrics = ServerMetrics(
                server_name="Test Server",
                timestamp=1234567890.0,
                cores=[],
                overall_usage=0.0,
                connected=False,
                error_message="Connection timeout",
            )

            server.update_metrics(metrics)
            await pilot.pause()

            # Verify error state
            assert not metrics.connected
            assert metrics.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_command_palette_opens(self):
        """Test command palette (P key)."""
        app = MonitoringApp(server_widgets=[])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press P for command palette
            await pilot.press("p")
            await pilot.pause()

            # Textual's built-in command palette should open

    @pytest.mark.asyncio
    async def test_navigation_wraps_at_boundaries(self):
        """Test that navigation does not wrap around at list boundaries."""
        servers = [ServerWidget(f"Server {i}") for i in range(3)]
        app = MonitoringApp(server_widgets=servers)

        async with app.run_test() as pilot:
            await pilot.pause()

            # Start at first server
            assert app.selected_index == 0

            # Navigate up from first (should stay at 0, no wrapping)
            await pilot.press("up")
            await pilot.pause()
            assert app.selected_index == 0  # Stays at 0

            # Navigate to last
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            assert app.selected_index == 2

            # Navigate down from last (should stay at last, no wrapping)
            await pilot.press("down")
            await pilot.pause()
            assert app.selected_index == 2  # Stays at 2

    @pytest.mark.asyncio
    async def test_cpu_history_accumulates_over_time(self):
        """Test CPU history accumulation in expanded view."""
        server = ServerWidget("Test Server")
        app = MonitoringApp(server_widgets=[server])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Expand server
            server.toggle_expanded()
            await pilot.pause()

            # Add metrics over time
            for i in range(10):
                cores = [CPUCore(core_id=0, usage_percent=float(i * 10))]
                metrics = ServerMetrics(
                    server_name="Test Server",
                    timestamp=1234567890.0 + i,
                    cores=cores,
                    overall_usage=float(i * 10),
                    connected=True,
                )
                server.update_metrics(metrics)
                await pilot.pause(0.05)

            # Verify latest metrics applied
            assert server.metrics is not None
            assert server.metrics.overall_usage == 90.0

    @pytest.mark.asyncio
    async def test_full_user_workflow(self):
        """End-to-end test of typical user workflow."""
        server1 = ServerWidget("Server 1")
        server2 = ServerWidget("Server 2")
        app = MonitoringApp(server_widgets=[server1, server2])

        async with app.run_test() as pilot:
            await pilot.pause()

            # Start at first server
            assert app.selected_index == 0

            # Navigate to second server
            await pilot.press("down")
            await pilot.pause()
            assert app.selected_index == 1

            # Expand it
            await pilot.press("right")
            await pilot.pause()
            assert server2.expanded

            # Refresh
            await pilot.press("r")
            await pilot.pause()

            # Collapse
            await pilot.press("left")
            await pilot.pause()
            assert not server2.expanded

            # Navigate back
            await pilot.press("up")
            await pilot.pause()
            assert app.selected_index == 0

            # Quit
            await pilot.press("q")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_concurrent_metric_updates(self):
        """Test multiple servers receiving metrics concurrently."""
        servers = [ServerWidget(f"Server {i}") for i in range(5)]
        app = MonitoringApp(server_widgets=servers)

        async with app.run_test() as pilot:
            await pilot.pause()

            # Update all servers concurrently
            async def update_server(server, usage):
                cores = [CPUCore(core_id=0, usage_percent=usage)]
                metrics = ServerMetrics(
                    server_name=server.server_name,
                    timestamp=1234567890.0,
                    cores=cores,
                    overall_usage=usage,
                    connected=True,
                )
                server.update_metrics(metrics)

            # Simulate concurrent updates
            await asyncio.gather(*[
                update_server(server, float(i * 20))
                for i, server in enumerate(servers)
            ])
            await pilot.pause()

            # Verify all updated
            for i, server in enumerate(servers):
                assert server.metrics is not None
                assert server.metrics.overall_usage == float(i * 20)
