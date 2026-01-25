"""Tests for concurrent operations in monitoring."""

import asyncio

import pytest

from src.monitor import CPUMonitor
from src.ssh_client import ServerConfig, SSHClient


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent operations in monitor."""

    async def test_concurrent_metric_collection(self):
        """Test that concurrent metric collection is handled properly."""
        config = ServerConfig(
            name="concurrent-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.1, max_history_seconds=10)

        # Try to collect metrics concurrently (should be protected by internal logic)
        tasks = [monitor.collect_metrics() for _ in range(10)]
        metrics_list = await asyncio.gather(*tasks, return_exceptions=True)

        # All should return metrics (even if not connected)
        assert all(m is not None for m in metrics_list if not isinstance(m, Exception))

        # None should raise exceptions
        assert not any(isinstance(m, Exception) for m in metrics_list)

    async def test_start_stop_concurrent_calls(self):
        """Test concurrent start/stop calls don't cause issues."""
        config = ServerConfig(
            name="start-stop-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.5, max_history_seconds=10)

        # Start multiple times concurrently
        start_tasks = [asyncio.create_task(monitor.start()) for _ in range(3)]

        await asyncio.sleep(0.5)

        # Stop multiple times concurrently
        stop_tasks = [asyncio.create_task(monitor.stop()) for _ in range(3)]

        # All should complete without errors
        await asyncio.gather(*start_tasks, *stop_tasks, return_exceptions=False)

    async def test_history_access_during_updates(self):
        """Test accessing history while it's being updated."""
        config = ServerConfig(
            name="history-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.1, max_history_seconds=10)

        # Start monitoring task
        monitor_task = asyncio.create_task(monitor.start())

        # Repeatedly access history while monitoring is running
        for _ in range(20):
            history = monitor.get_cpu_history()
            assert isinstance(history, list)
            await asyncio.sleep(0.05)

        # Stop monitoring
        await monitor.stop()
        await monitor_task

    async def test_multiple_monitors_same_client(self):
        """Test that multiple monitors with same client don't interfere."""
        config = ServerConfig(
            name="multi-monitor-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # Create multiple monitors (though unusual, should be handled)
        monitor1 = CPUMonitor(client, poll_interval=0.2, max_history_seconds=10)
        monitor2 = CPUMonitor(client, poll_interval=0.3, max_history_seconds=10)

        # Start both
        task1 = asyncio.create_task(monitor1.start())
        task2 = asyncio.create_task(monitor2.start())

        await asyncio.sleep(1)

        # Stop both
        await monitor1.stop()
        await monitor2.stop()

        await asyncio.gather(task1, task2, return_exceptions=True)

    async def test_rapid_connect_disconnect(self):
        """Test rapid connection and disconnection cycles."""
        config = ServerConfig(
            name="rapid-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # Rapidly connect and disconnect
        for _ in range(5):
            await client.connect()
            await client.disconnect()

        # Should end in disconnected state
        assert not await client.is_connected()

    async def test_concurrent_command_execution(self):
        """Test that concurrent command execution is properly queued."""
        config = ServerConfig(
            name="command-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # Try to execute multiple commands concurrently (should be protected by lock)
        tasks = [
            client.execute_command("cat /proc/stat"),
            client.execute_command("cat /proc/meminfo"),
            client.execute_command("uptime"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should return None (not connected), but no exceptions
        assert all(r is None for r in results)
        assert all(not isinstance(r, Exception) for r in results)

    async def test_monitor_with_rapid_metric_requests(self):
        """Test monitor handling rapid metric requests."""
        config = ServerConfig(
            name="rapid-metrics-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.5, max_history_seconds=10)

        # Request metrics rapidly
        tasks = [monitor.collect_metrics() for _ in range(50)]
        metrics_list = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete successfully
        assert len(metrics_list) == 50
        assert all(not isinstance(m, Exception) for m in metrics_list)

    async def test_cleanup_during_active_monitoring(self):
        """Test cleanup while monitoring is active."""
        config = ServerConfig(
            name="cleanup-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.2, max_history_seconds=10)

        # Start monitoring
        monitor_task = asyncio.create_task(monitor.start())

        await asyncio.sleep(0.3)

        # Immediately stop and cleanup
        await monitor.stop()
        await client.disconnect()

        # Monitor task should complete without hanging
        try:
            await asyncio.wait_for(monitor_task, timeout=2)
        except TimeoutError:
            pytest.fail("Monitor task did not complete during cleanup")
