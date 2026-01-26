"""Integration tests for network failure scenarios."""

import asyncio

import pytest

from src.monitor import CPUMonitor
from src.ssh_client import ServerConfig, SSHClient


@pytest.mark.asyncio
class TestNetworkFailures:
    """Test handling of network failures during monitoring."""

    async def test_connection_timeout(self):
        """Test handling of connection timeout."""
        # Use an unreachable host (IP in TEST-NET-1 range, RFC 5737)
        config = ServerConfig(
            name="timeout-test",
            host="192.0.2.1",  # Reserved for documentation/testing
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=2, max_retries=1, retry_delay=0)

        # Should fail to connect
        result = await client.connect()
        assert not result
        assert not client.status.connected
        assert client.status.error_message is not None

    async def test_connection_refused(self):
        """Test handling of connection refused."""
        config = ServerConfig(
            name="refused-test",
            host="127.0.0.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        # Use a port that's likely not running SSH (port 9999)
        # Note: This test assumes no SSH server on port 9999
        client = SSHClient(config, connection_timeout=2, max_retries=1, retry_delay=0)

        result = await client.connect()
        assert not result
        assert not client.status.connected

    async def test_monitor_handles_connection_loss(self):
        """Test monitor gracefully handles connection loss during monitoring."""
        config = ServerConfig(
            name="disconnect-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)
        monitor = CPUMonitor(client, poll_interval=0.5, history_window=10)

        # Start monitoring (will fail to connect but shouldn't crash)
        monitor_task = asyncio.create_task(monitor.start())

        # Let it try a few times
        await asyncio.sleep(2)

        # Stop monitoring
        await monitor.stop()

        # Should complete without exceptions
        try:
            await asyncio.wait_for(monitor_task, timeout=2)
        except TimeoutError:
            pytest.fail("Monitor task did not complete in time")

    async def test_concurrent_connection_attempts(self):
        """Test handling of concurrent connection attempts."""
        config = ServerConfig(
            name="concurrent-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # Try multiple concurrent connections
        tasks = [client.connect() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail (unreachable host)
        assert all(not r for r in results if isinstance(r, bool))
        # Should not have any exceptions (all handled properly)
        assert all(isinstance(r, bool) for r in results)

    async def test_monitor_consecutive_failures(self):
        """Test monitor handles consecutive failures gracefully."""
        config = ServerConfig(
            name="failures-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # Create monitor with fast poll interval
        monitor = CPUMonitor(
            client,
            poll_interval=0.1,
            history_window=10,
        )

        # Start monitoring in the background
        monitor_task = asyncio.create_task(monitor.start())

        # Let it run for a bit (will have consecutive failures due to unreachable host)
        await asyncio.sleep(0.5)

        # Stop monitoring
        await monitor.stop()

        # Monitor task should complete without hanging
        try:
            await asyncio.wait_for(monitor_task, timeout=2)
        except TimeoutError:
            pytest.fail("Monitor task did not complete in time")

    async def test_ensure_connected_after_disconnect(self):
        """Test ensure_connected attempts reconnection."""
        config = ServerConfig(
            name="reconnect-test",
            host="192.0.2.1",
            username="testuser",
            auth_method="password",
            password="testpass",
        )

        client = SSHClient(config, connection_timeout=1, max_retries=1, retry_delay=0)

        # First connection attempt fails
        await client.ensure_connected()
        assert not await client.is_connected()

        # Second attempt also fails (host still unreachable)
        result = await client.ensure_connected()
        assert not result
        assert not await client.is_connected()
