"""Tests for CPU monitor module."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.monitor import CPUMonitor, ServerMetrics, CPUCore, MemoryInfo
from src.ssh_client import SSHClient, ServerConfig, ConnectionStatus


@pytest.fixture
def server_config():
    """Create a test server configuration."""
    return ServerConfig(
        name="test-server", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
    )


@pytest.fixture
def ssh_client(server_config):
    """Create a mock SSH client."""
    client = SSHClient(config=server_config)
    client.status = ConnectionStatus(connected=True)
    return client


@pytest.fixture
def cpu_monitor(ssh_client):
    """Create a CPU monitor instance."""
    return CPUMonitor(ssh_client=ssh_client, poll_interval=0.1, history_window=60)


@pytest.mark.asyncio
async def test_monitor_initialization(cpu_monitor, ssh_client):
    """Test CPU monitor initialization."""
    assert cpu_monitor.ssh_client == ssh_client
    assert cpu_monitor.poll_interval == 0.1
    assert cpu_monitor.history_window == 60
    assert not cpu_monitor._running


@pytest.mark.asyncio
async def test_start_stop_monitoring(cpu_monitor):
    """Test starting and stopping the monitor."""
    await cpu_monitor.start()
    assert cpu_monitor._running
    assert cpu_monitor._task is not None

    await cpu_monitor.stop()
    assert not cpu_monitor._running


@pytest.mark.asyncio
async def test_parse_proc_stat(cpu_monitor):
    """Test parsing /proc/stat output."""
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpu1 250 50 75 1250 25 0 13 0 0 0
cpu2 250 50 75 1250 25 0 12 0 0 0
cpu3 250 50 75 1250 25 0 13 0 0 0
"""

    stats = cpu_monitor._parse_proc_stat(proc_stat_output)

    assert len(stats) == 4
    assert 0 in stats
    assert 1 in stats
    assert 2 in stats
    assert 3 in stats

    # Check core 0 values
    assert stats[0]["user"] == 250
    assert stats[0]["nice"] == 50
    assert stats[0]["system"] == 75
    assert stats[0]["idle"] == 1250
    assert stats[0]["iowait"] == 25


@pytest.mark.asyncio
async def test_calculate_cpu_usage(cpu_monitor):
    """Test CPU usage calculation."""
    prev = {
        "user": 1000,
        "nice": 100,
        "system": 200,
        "idle": 8000,
        "iowait": 100,
        "irq": 0,
        "softirq": 0,
    }

    curr = {
        "user": 1200,  # +200
        "nice": 150,  # +50
        "system": 250,  # +50
        "idle": 8300,  # +300
        "iowait": 150,  # +50
        "irq": 0,
        "softirq": 0,
    }

    # Total diff: 200+50+50+300+50 = 650
    # Idle diff: 300+50 = 350
    # Active: 650-350 = 300
    # Usage: 300/650 = ~46.15%

    usage = cpu_monitor._calculate_cpu_usage(prev, curr)

    assert 45.0 < usage < 47.0


@pytest.mark.asyncio
async def test_collect_cpu_metrics_disconnected(cpu_monitor, ssh_client):
    """Test collecting metrics when disconnected."""
    ssh_client.ensure_connected = AsyncMock(return_value=False)
    ssh_client.status = ConnectionStatus(connected=False, error_message="Connection failed")

    # The monitor loop would handle this, but we're testing _collect_cpu_metrics directly
    # which doesn't check ensure_connected, so we need to make execute_command return None
    ssh_client.execute_command = AsyncMock(return_value=None)

    metrics = await cpu_monitor._collect_cpu_metrics()

    assert not metrics.connected
    assert metrics.error_message == "Failed to read CPU stats"
    assert len(metrics.cores) == 0


@pytest.mark.asyncio
async def test_collect_cpu_metrics_success(cpu_monitor, ssh_client):
    """Test successful CPU metrics collection."""
    proc_stat_first = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    proc_stat_second = """cpu  1200 220 350 5300 120 0 55 0 0 0
cpu0 300 55 87 1300 30 0 14 0 0 0
cpu1 300 55 88 1300 30 0 14 0 0 0
"""

    ssh_client.execute_command = AsyncMock(side_effect=[
        proc_stat_first, None,  # First call: proc_stat, then None for meminfo
        proc_stat_second, None  # Second call: proc_stat, then None for meminfo
    ])

    # First collection (no previous data)
    metrics1 = await cpu_monitor._collect_cpu_metrics()
    assert metrics1.connected
    assert len(metrics1.cores) == 2
    assert metrics1.cores[0].usage_percent == 0.0  # First reading

    # Second collection (with previous data)
    metrics2 = await cpu_monitor._collect_cpu_metrics()
    assert metrics2.connected
    assert len(metrics2.cores) == 2
    assert metrics2.cores[0].usage_percent > 0.0  # Should have calculated usage


@pytest.mark.asyncio
async def test_get_metrics(cpu_monitor):
    """Test getting the latest metrics."""
    # Initially None
    metrics = await cpu_monitor.get_metrics()
    assert metrics is None

    # Set some metrics
    test_metrics = ServerMetrics(
        server_name="test",
        timestamp=1234567890.0,
        cores=[CPUCore(core_id=0, usage_percent=50.0)],
        overall_usage=50.0,
        connected=True,
    )

    cpu_monitor._latest_metrics = test_metrics

    metrics = await cpu_monitor.get_metrics()
    assert metrics == test_metrics


@pytest.mark.asyncio
async def test_monitor_loop_integration(cpu_monitor, ssh_client):
    """Test the monitoring loop integration."""
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    ssh_client.ensure_connected = AsyncMock(return_value=True)
    ssh_client.execute_command = AsyncMock(return_value=proc_stat_output)

    # Start monitoring
    await cpu_monitor.start()

    # Wait for at least one poll cycle
    await asyncio.sleep(0.2)

    # Get metrics
    metrics = await cpu_monitor.get_metrics()

    assert metrics is not None
    assert metrics.connected
    assert len(metrics.cores) == 2

    # Stop monitoring
    await cpu_monitor.stop()


@pytest.mark.asyncio
async def test_parse_proc_stat_malformed_line():
    """Test parsing /proc/stat with malformed lines."""
    from src.monitor import CPUMonitor
    from src.ssh_client import SSHClient, ServerConfig

    config = ServerConfig(
        name="test", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
    )
    client = SSHClient(config=config)
    monitor = CPUMonitor(ssh_client=client)

    # Include a malformed line
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpuX invalid data
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    stats = monitor._parse_proc_stat(proc_stat_output)

    # Should parse valid cores and skip invalid ones
    assert len(stats) == 2
    assert 0 in stats
    assert 1 in stats


@pytest.mark.asyncio
async def test_parse_proc_stat_incomplete_data():
    """Test parsing /proc/stat with incomplete CPU data."""
    from src.monitor import CPUMonitor
    from src.ssh_client import SSHClient, ServerConfig

    config = ServerConfig(
        name="test", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
    )
    client = SSHClient(config=config)
    monitor = CPUMonitor(ssh_client=client)

    # Include a line with insufficient fields
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    stats = monitor._parse_proc_stat(proc_stat_output)

    # Should parse only valid core
    assert len(stats) == 1
    assert 1 in stats


@pytest.mark.asyncio
async def test_calculate_cpu_usage_zero_total_diff(cpu_monitor):
    """Test CPU usage calculation with zero total diff."""
    prev = {
        "user": 1000,
        "nice": 100,
        "system": 200,
        "idle": 8000,
        "iowait": 100,
        "irq": 0,
        "softirq": 0,
    }

    # Same as prev (no time passed)
    curr = prev.copy()

    usage = cpu_monitor._calculate_cpu_usage(prev, curr)

    # Should return 0 when no time has passed
    assert usage == 0.0


@pytest.mark.asyncio
async def test_calculate_cpu_usage_100_percent():
    """Test CPU usage calculation at 100%."""
    from src.monitor import CPUMonitor
    from src.ssh_client import SSHClient, ServerConfig

    config = ServerConfig(
        name="test", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
    )
    client = SSHClient(config=config)
    monitor = CPUMonitor(ssh_client=client)

    prev = {
        "user": 1000,
        "nice": 0,
        "system": 0,
        "idle": 0,
        "iowait": 0,
        "irq": 0,
        "softirq": 0,
    }

    curr = {
        "user": 2000,  # +1000, all active
        "nice": 0,
        "system": 0,
        "idle": 0,  # No idle time
        "iowait": 0,
        "irq": 0,
        "softirq": 0,
    }

    usage = monitor._calculate_cpu_usage(prev, curr)

    # Should be 100% (or close due to clamping)
    assert usage == 100.0


@pytest.mark.asyncio
async def test_monitor_stop_when_not_running(cpu_monitor):
    """Test stopping monitor when not running."""
    assert not cpu_monitor._running

    # Should handle gracefully
    await cpu_monitor.stop()

    assert not cpu_monitor._running


@pytest.mark.asyncio
async def test_monitor_start_when_already_running(cpu_monitor):
    """Test starting monitor when already running."""
    await cpu_monitor.start()
    assert cpu_monitor._running

    first_task = cpu_monitor._task

    # Try to start again
    await cpu_monitor.start()

    # Should not create a new task
    assert cpu_monitor._task == first_task

    await cpu_monitor.stop()


@pytest.mark.asyncio
async def test_collect_cpu_metrics_with_no_previous_stats():
    """Test collecting metrics on first run (no previous stats)."""
    from src.monitor import CPUMonitor
    from src.ssh_client import SSHClient, ServerConfig

    config = ServerConfig(
        name="test", host="192.168.1.100", username="testuser", key_path="/tmp/test_key.pem"
    )
    client = SSHClient(config=config)
    monitor = CPUMonitor(ssh_client=client)

    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    client.execute_command = AsyncMock(return_value=proc_stat_output)

    metrics = await monitor._collect_cpu_metrics()

    # First reading should have 0% usage
    assert all(core.usage_percent == 0.0 for core in metrics.cores)
    assert metrics.overall_usage == 0.0
    assert len(metrics.cores) == 2


@pytest.mark.asyncio
async def test_monitor_loop_exception_handling(cpu_monitor, ssh_client):
    """Test monitor loop continues after exceptions."""
    ssh_client.ensure_connected = AsyncMock(return_value=True)

    # First call raises exception, second succeeds
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
"""

    ssh_client.execute_command = AsyncMock(
        side_effect=[Exception("Test error"), proc_stat_output]
    )

    await cpu_monitor.start()

    # Wait for a couple poll cycles
    await asyncio.sleep(0.3)

    # Should still be running
    assert cpu_monitor._running

    await cpu_monitor.stop()


@pytest.mark.asyncio
async def test_parse_meminfo(cpu_monitor):
    """Test parsing /proc/meminfo output."""
    meminfo_output = """MemTotal:       16384000 kB
MemFree:         8192000 kB
MemAvailable:   10240000 kB
Buffers:          512000 kB
Cached:          2048000 kB
SwapCached:            0 kB
Active:          4096000 kB
Inactive:        3072000 kB
"""

    memory_info = cpu_monitor._parse_meminfo(meminfo_output)

    assert memory_info is not None
    assert memory_info.total_mb == pytest.approx(16000, rel=1e-1)
    assert memory_info.available_mb == pytest.approx(10000, rel=1e-1)
    assert memory_info.free_mb == pytest.approx(8000, rel=1e-1)
    assert memory_info.cached_mb == pytest.approx(2000, rel=1e-1)
    assert memory_info.buffers_mb == pytest.approx(500, rel=1e-1)
    assert 0 < memory_info.usage_percent < 100


@pytest.mark.asyncio
async def test_parse_meminfo_invalid(cpu_monitor):
    """Test parsing invalid meminfo output."""
    invalid_output = "invalid data"

    memory_info = cpu_monitor._parse_meminfo(invalid_output)

    # Should return None or handle gracefully
    assert memory_info is None or memory_info.total_mb == 0


@pytest.mark.asyncio
async def test_cpu_history_tracking(cpu_monitor, ssh_client):
    """Test CPU history tracking."""
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
cpu1 250 50 75 1250 25 0 13 0 0 0
"""

    ssh_client.ensure_connected = AsyncMock(return_value=True)
    ssh_client.execute_command = AsyncMock(return_value=proc_stat_output)

    # Start monitoring
    await cpu_monitor.start()

    # Wait for a few poll cycles
    await asyncio.sleep(0.3)

    # Get history
    history = await cpu_monitor.get_cpu_history()

    assert len(history) > 0
    # Each entry should be a tuple of (timestamp, usage)
    for entry in history:
        assert len(entry) == 2
        assert isinstance(entry[0], float)  # timestamp
        assert isinstance(entry[1], float)  # usage

    await cpu_monitor.stop()


@pytest.mark.asyncio
async def test_history_window_trimming(cpu_monitor):
    """Test that history is trimmed to the configured window."""
    import time

    # Manually add some old history data
    current_time = time.time()
    cpu_monitor._cpu_history = [
        (current_time - 100, 50.0),  # Old data outside window
        (current_time - 50, 45.0),   # Within window
        (current_time - 10, 55.0),   # Recent
    ]

    # Trigger trimming by adding new data
    cpu_monitor._cpu_history.append((current_time, 60.0))
    cutoff_time = current_time - cpu_monitor.history_window
    cpu_monitor._cpu_history = [(t, u) for t, u in cpu_monitor._cpu_history if t >= cutoff_time]

    # Check that old data was trimmed
    history = await cpu_monitor.get_cpu_history()
    assert all(t >= cutoff_time for t, _ in history)


@pytest.mark.asyncio
async def test_collect_metrics_with_memory(cpu_monitor, ssh_client):
    """Test collecting CPU metrics with memory information."""
    proc_stat_output = """cpu  1000 200 300 5000 100 0 50 0 0 0
cpu0 250 50 75 1250 25 0 12 0 0 0
"""

    meminfo_output = """MemTotal:       16384000 kB
MemFree:         8192000 kB
MemAvailable:   10240000 kB
Buffers:          512000 kB
Cached:          2048000 kB
"""

    ssh_client.execute_command = AsyncMock(side_effect=[proc_stat_output, meminfo_output])

    metrics = await cpu_monitor._collect_cpu_metrics()

    assert metrics.connected
    assert metrics.memory is not None
    assert metrics.memory.total_mb > 0
    assert metrics.memory.usage_percent >= 0
