"""Tests for main application module."""

import asyncio
import contextlib
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml

from src.main import CPUMonitoringApp
from src.monitor import CPUMonitor
from src.ssh_client import SSHClient
from src.ui import ServerWidget


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    config_data = {
        "servers": [
            {
                "name": "test-server1",
                "host": "192.168.1.100",
                "username": "testuser",
                "auth_method": "key",
                "key_path": "/tmp/test_key.pem",
            },
            {
                "name": "test-server2",
                "host": "192.168.1.101",
                "username": "testuser",
                "auth_method": "key",
                "key_path": "/tmp/test_key.pem",
            },
        ],
        "monitoring": {
            "poll_interval": 2.0,
            "connection_timeout": 10,
            "max_retries": 3,
            "retry_delay": 5,
            "ui_refresh_interval": 0.5,
        },
        "display": {
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def app(temp_config_file):
    """Create a CPUMonitoringApp instance."""
    return CPUMonitoringApp(config_path=temp_config_file)


def test_app_initialization(app, temp_config_file):
    """Test app initialization."""
    assert app.config_path == temp_config_file
    assert app.config == {"servers": [], "monitoring": {}, "display": {}}
    assert app.ssh_clients == []
    assert app.monitors == []
    assert app.server_widgets == []
    assert app.ui_app is None
    assert app._ui_update_task is None
    assert not app._running


def test_load_config(app):
    """Test loading configuration from file."""
    app.load_config()

    assert "servers" in app.config
    assert len(app.config["servers"]) == 2
    assert app.config["servers"][0]["name"] == "test-server1"
    assert app.config["servers"][1]["name"] == "test-server2"
    assert "monitoring" in app.config
    assert "display" in app.config


def test_load_config_file_not_found():
    """Test loading config when file doesn't exist."""
    app = CPUMonitoringApp(config_path="nonexistent.yaml")

    with pytest.raises(SystemExit):
        app.load_config()


def test_load_config_invalid_yaml():
    """Test loading invalid YAML config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_path = f.name

    try:
        app = CPUMonitoringApp(config_path=temp_path)
        with pytest.raises(SystemExit):
            app.load_config()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_load_config_missing_servers():
    """Test loading config without servers section."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"monitoring": {}}, f)
        temp_path = f.name

    try:
        app = CPUMonitoringApp(config_path=temp_path)
        with pytest.raises(SystemExit):
            app.load_config()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_load_config_empty_servers():
    """Test loading config with empty servers list."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"servers": []}, f)
        temp_path = f.name

    try:
        app = CPUMonitoringApp(config_path=temp_path)
        with pytest.raises(SystemExit):
            app.load_config()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_initialize_components(app):
    """Test initializing SSH clients, monitors, and widgets."""
    app.load_config()
    app.initialize_components()

    # Check that components were created
    assert len(app.ssh_clients) == 2
    assert len(app.monitors) == 2
    assert len(app.server_widgets) == 2

    # Check SSH clients
    assert all(isinstance(client, SSHClient) for client in app.ssh_clients)
    assert app.ssh_clients[0].config.name == "test-server1"
    assert app.ssh_clients[1].config.name == "test-server2"

    # Check monitors
    assert all(isinstance(monitor, CPUMonitor) for monitor in app.monitors)
    assert app.monitors[0].poll_interval == 2.0

    # Check widgets
    assert all(isinstance(widget, ServerWidget) for widget in app.server_widgets)
    assert app.server_widgets[0].server_name == "test-server1"


def test_initialize_components_with_defaults(temp_config_file):
    """Test initializing components with default configuration values."""
    # Create minimal config
    config_data = {
        "servers": [
            {
                "name": "test-server",
                "host": "192.168.1.100",
                "username": "testuser",
                "auth_method": "key",
                "key_path": "/tmp/test_key.pem",
            }
        ]
    }

    with open(temp_config_file, "w") as f:
        yaml.dump(config_data, f)

    app = CPUMonitoringApp(config_path=temp_config_file)
    app.load_config()
    app.initialize_components()

    # Check defaults were applied
    assert app.monitors[0].poll_interval == 2.0  # Default
    assert app.ssh_clients[0].connection_timeout == 10  # Default


def test_initialize_components_missing_field():
    """Test initializing with missing required field in server config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {
            "servers": [
                {
                    "name": "test-server",
                    "host": "192.168.1.100",
                    # Missing username and key_path
                }
            ]
        }
        yaml.dump(config_data, f)
        temp_path = f.name

    try:
        app = CPUMonitoringApp(config_path=temp_path)
        app.load_config()
        with pytest.raises(SystemExit):
            app.initialize_components()
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_start_monitoring(app):
    """Test starting monitoring for all servers."""
    app.load_config()
    app.initialize_components()

    # Mock monitor methods
    for monitor in app.monitors:
        monitor.start = AsyncMock()

    await app.start_monitoring()

    # Verify all monitors started
    for monitor in app.monitors:
        monitor.start.assert_called_once()

    # Note: Connection logic now happens inside monitor.start(),
    # so we no longer directly verify client.connect() calls here


@pytest.mark.asyncio
async def test_start_monitoring_connection_failure(app):
    """Test starting monitoring when some connections fail."""
    app.load_config()
    app.initialize_components()

    # First client succeeds, second fails
    app.ssh_clients[0].connect = AsyncMock(return_value=True)
    app.ssh_clients[1].connect = AsyncMock(return_value=False)

    for monitor in app.monitors:
        monitor.start = AsyncMock()

    await app.start_monitoring()

    # All monitors should still start (they handle disconnections)
    for monitor in app.monitors:
        monitor.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_monitoring(app):
    """Test stopping all monitoring."""
    app.load_config()
    app.initialize_components()

    # Mock methods
    for monitor in app.monitors:
        monitor.stop = AsyncMock()

    for client in app.ssh_clients:
        client.disconnect = AsyncMock()

    # Create a mock UI update task
    app._ui_update_task = asyncio.create_task(asyncio.sleep(10))

    await app.stop_monitoring()

    # Verify all monitors stopped
    for monitor in app.monitors:
        monitor.stop.assert_called_once()

    # Verify all clients disconnected
    for client in app.ssh_clients:
        client.disconnect.assert_called_once()

    # Verify UI task was cancelled
    assert app._ui_update_task.cancelled()


def test_save_config(app):
    """Test saving configuration to file."""
    app.load_config()
    app.config["servers"].append({
        "name": "new-server",
        "host": "192.168.1.102",
        "username": "testuser",
        "auth_method": "key",
        "key_path": "/tmp/test_key.pem",
    })

    app.save_config()

    # Reload and verify
    with open(app.config_path) as f:
        saved_config = yaml.safe_load(f)

    assert len(saved_config["servers"]) == 3
    assert saved_config["servers"][2]["name"] == "new-server"


def test_save_config_error(app, tmp_path):
    """Test saving config when write fails."""
    app.load_config()
    # Point to a directory (can't write to a directory)
    app.config_path = str(tmp_path)

    # Should not raise, just log error
    app.save_config()


def test_delete_server(app):
    """Test deleting a server."""
    app.load_config()
    app.initialize_components()

    initial_server_count = len(app.ssh_clients)

    # Mock the cleanup task
    with patch.object(asyncio, "create_task") as mock_create_task:
        app.delete_server("test-server1")

        # Verify server removed from config
        assert len(app.config["servers"]) == 1
        assert app.config["servers"][0]["name"] == "test-server2"

        # Verify components removed
        assert len(app.ssh_clients) == initial_server_count - 1
        assert len(app.monitors) == initial_server_count - 1
        assert len(app.server_widgets) == initial_server_count - 1

        # Verify cleanup task created
        mock_create_task.assert_called_once()


def test_delete_nonexistent_server(app):
    """Test deleting a server that doesn't exist."""
    app.load_config()
    app.initialize_components()

    initial_count = len(app.ssh_clients)

    app.delete_server("nonexistent-server")

    # No components should be removed
    assert len(app.ssh_clients) == initial_count
    assert len(app.monitors) == initial_count
    assert len(app.server_widgets) == initial_count


@pytest.mark.asyncio
async def test_cleanup_server(app):
    """Test cleanup of server resources."""
    app.load_config()
    app.initialize_components()

    monitor = app.monitors[0]
    ssh_client = app.ssh_clients[0]

    monitor.stop = AsyncMock()
    ssh_client.disconnect = AsyncMock()

    await app._cleanup_server(monitor, ssh_client)

    monitor.stop.assert_called_once()
    ssh_client.disconnect.assert_called_once()


def test_add_server(app):
    """Test adding a new server."""
    app.load_config()
    app.initialize_components()

    initial_count = len(app.ssh_clients)

    new_server = {
        "name": "new-server",
        "host": "192.168.1.102",
        "username": "testuser",
        "auth_method": "key",
        "key_path": "/tmp/test_key.pem",
    }

    # Mock UI app
    app.ui_app = MagicMock()
    app.ui_app.add_server_widget = Mock()

    with patch.object(asyncio, "create_task") as mock_create_task:
        app.add_server(new_server)

        # Verify server added to config
        assert len(app.config["servers"]) == initial_count + 1
        assert app.config["servers"][-1]["name"] == "new-server"

        # Verify components created
        assert len(app.ssh_clients) == initial_count + 1
        assert len(app.monitors) == initial_count + 1
        assert len(app.server_widgets) == initial_count + 1

        # Verify widget added to UI
        app.ui_app.add_server_widget.assert_called_once()

        # Verify monitoring task created
        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_start_server_monitoring(app):
    """Test starting monitoring for a new server."""
    app.load_config()
    app.initialize_components()

    ssh_client = app.ssh_clients[0]
    monitor = app.monitors[0]

    ssh_client.connect = AsyncMock(return_value=True)
    monitor.start = AsyncMock()

    await app._start_server_monitoring(ssh_client, monitor)

    ssh_client.connect.assert_called_once()
    monitor.start.assert_called_once()


@pytest.mark.asyncio
async def test_ui_update_loop(app):
    """Test UI update loop."""
    app.load_config()
    app.initialize_components()

    # Set a fast refresh interval for testing
    app.config.setdefault("monitoring", {})["ui_refresh_interval"] = 0.01

    # Mock monitors to return metrics
    from src.monitor import CPUCore, ServerMetrics

    test_metrics = ServerMetrics(
        server_name="test",
        timestamp=1234567890.0,
        cores=[CPUCore(core_id=0, usage_percent=50.0)],
        overall_usage=50.0,
        connected=True,
    )

    for monitor in app.monitors:
        monitor.get_metrics = AsyncMock(return_value=test_metrics)

    # Mock widget update methods
    for widget in app.server_widgets:
        widget.update_metrics = Mock()

    app._running = True

    # Run loop for a short time
    loop_task = asyncio.create_task(app.ui_update_loop())
    await asyncio.sleep(0.05)  # Let it run a couple iterations
    app._running = False

    # Wait for loop to finish
    try:
        await asyncio.wait_for(loop_task, timeout=0.1)
    except TimeoutError:
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop_task

    # Verify widgets were updated
    for widget in app.server_widgets:
        assert widget.update_metrics.call_count >= 1


@pytest.mark.asyncio
async def test_ui_update_loop_cancellation(app):
    """Test UI update loop handles cancellation."""
    app.load_config()
    app.initialize_components()

    app._running = True
    loop_task = asyncio.create_task(app.ui_update_loop())

    # Cancel the task
    loop_task.cancel()

    # Should handle cancellation gracefully
    with pytest.raises(asyncio.CancelledError):
        await loop_task


@pytest.mark.asyncio
async def test_ui_update_loop_with_error(app):
    """Test UI update loop handles errors gracefully."""
    app.load_config()
    app.initialize_components()

    # Set a fast refresh interval for testing
    app.config.setdefault("monitoring", {})["ui_refresh_interval"] = 0.01

    error_count = 0

    async def mock_get_metrics_with_limit():
        nonlocal error_count
        error_count += 1
        if error_count > 3:  # After 3 errors, stop the loop
            app._running = False
        raise Exception("Test error")

    # Make get_metrics raise an error
    for monitor in app.monitors:
        monitor.get_metrics = mock_get_metrics_with_limit

    app._running = True

    # Run loop
    loop_task = asyncio.create_task(app.ui_update_loop())

    # Wait for loop to finish with errors
    try:
        await asyncio.wait_for(loop_task, timeout=1.0)
    except TimeoutError:
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop_task

    # Should have encountered errors but not crashed
    assert error_count >= 3


@pytest.mark.asyncio
async def test_run_async(app):
    """Test async run method."""
    app.load_config()
    app.initialize_components()

    # Mock all the methods and tasks
    app.start_monitoring = AsyncMock()
    app.stop_monitoring = AsyncMock()
    app.ui_update_loop = AsyncMock()

    # Mock the UI app
    mock_ui_app = MagicMock()
    mock_ui_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())

    with patch("src.main.MonitoringApp", return_value=mock_ui_app), contextlib.suppress(KeyboardInterrupt):
        await app.run_async()

    # Verify start was called
    app.start_monitoring.assert_called_once()

    # Verify stop was called (cleanup in finally)
    app.stop_monitoring.assert_called_once()


@pytest.mark.asyncio
async def test_run_async_handles_exception(app):
    """Test async run handles exceptions."""
    app.load_config()
    app.initialize_components()

    app.start_monitoring = AsyncMock()
    app.stop_monitoring = AsyncMock()
    app.ui_update_loop = AsyncMock()

    # Mock UI app to raise an error
    mock_ui_app = MagicMock()
    mock_ui_app.run_async = AsyncMock(side_effect=Exception("Test error"))

    with patch("src.main.MonitoringApp", return_value=mock_ui_app):
        await app.run_async()

    # Should still call stop_monitoring in cleanup
    app.stop_monitoring.assert_called_once()


def test_run(app):
    """Test synchronous run wrapper."""
    app.load_config()
    app.initialize_components()

    # Mock asyncio.run to avoid actually running
    with patch("asyncio.run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt()

        with contextlib.suppress(KeyboardInterrupt):
            app.run()

        mock_run.assert_called_once()


def test_run_handles_exception(app):
    """Test run handles exceptions."""
    app.load_config()
    app.initialize_components()

    # Mock asyncio.run to raise an error
    with patch("asyncio.run") as mock_run:
        mock_run.side_effect = Exception("Test error")

        with pytest.raises(SystemExit):
            app.run()
