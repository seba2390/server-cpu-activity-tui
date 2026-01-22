"""CPU monitoring logic for collecting and processing CPU metrics."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


@dataclass
class CPUCore:
    """CPU core information."""

    core_id: int
    usage_percent: float
    user: float = 0.0
    system: float = 0.0
    idle: float = 0.0


@dataclass
class ServerMetrics:
    """CPU metrics for a server."""

    server_name: str
    timestamp: float
    cores: list[CPUCore]
    overall_usage: float
    connected: bool
    error_message: Optional[str] = None

    @property
    def core_count(self) -> int:
        """Get number of CPU cores."""
        return len(self.cores)


class CPUMonitor:
    """Monitors CPU usage on remote servers via SSH."""

    def __init__(self, ssh_client: SSHClient, poll_interval: float = 2.0):
        """Initialize CPU monitor.

        Args:
            ssh_client: SSH client for server connection
            poll_interval: Interval between CPU polls in seconds
        """
        self.ssh_client = ssh_client
        self.poll_interval = poll_interval

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._latest_metrics: Optional[ServerMetrics] = None
        self._lock = asyncio.Lock()

        # For CPU usage calculation
        self._prev_stats: Optional[dict[int, dict[str, int]]] = None

    async def start(self):
        """Start monitoring CPU metrics."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"{self.ssh_client.config.name}: CPU monitoring started")

    async def stop(self):
        """Stop monitoring CPU metrics."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info(f"{self.ssh_client.config.name}: CPU monitoring stopped")

    async def get_metrics(self) -> Optional[ServerMetrics]:
        """Get the latest CPU metrics.

        Returns:
            Latest server metrics, or None if not available
        """
        async with self._lock:
            return self._latest_metrics

    async def _monitor_loop(self):
        """Main monitoring loop that periodically collects CPU data."""
        while self._running:
            try:
                # Ensure SSH connection is active
                if not await self.ssh_client.ensure_connected():
                    async with self._lock:
                        self._latest_metrics = ServerMetrics(
                            server_name=self.ssh_client.config.name,
                            timestamp=time.time(),
                            cores=[],
                            overall_usage=0.0,
                            connected=False,
                            error_message=self.ssh_client.status.error_message,
                        )

                    await asyncio.sleep(self.poll_interval)
                    continue

                # Collect CPU metrics
                metrics = await self._collect_cpu_metrics()

                async with self._lock:
                    self._latest_metrics = metrics

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"{self.ssh_client.config.name}: Error in monitoring loop: {e}", exc_info=True
                )

            await asyncio.sleep(self.poll_interval)

    async def _collect_cpu_metrics(self) -> ServerMetrics:
        """Collect CPU metrics from the remote server.

        Returns:
            ServerMetrics with current CPU usage data
        """
        try:
            # Read /proc/stat to get CPU usage
            output = await self.ssh_client.execute_command("cat /proc/stat")

            if output is None:
                return ServerMetrics(
                    server_name=self.ssh_client.config.name,
                    timestamp=time.time(),
                    cores=[],
                    overall_usage=0.0,
                    connected=False,
                    error_message="Failed to read CPU stats",
                )

            # Parse /proc/stat output
            current_stats = self._parse_proc_stat(output)

            # Calculate CPU usage based on difference from previous reading
            cores = []
            total_usage = 0.0

            if self._prev_stats is not None:
                for core_id, curr_stat in current_stats.items():
                    if core_id in self._prev_stats:
                        prev_stat = self._prev_stats[core_id]
                        usage = self._calculate_cpu_usage(prev_stat, curr_stat)

                        cores.append(
                            CPUCore(
                                core_id=core_id,
                                usage_percent=usage,
                                user=curr_stat.get("user", 0),
                                system=curr_stat.get("system", 0),
                                idle=curr_stat.get("idle", 0),
                            )
                        )

                        total_usage += usage
            else:
                # First reading, just create cores with 0% usage
                for core_id in current_stats.keys():
                    cores.append(CPUCore(core_id=core_id, usage_percent=0.0))

            # Store current stats for next calculation
            self._prev_stats = current_stats

            # Calculate overall usage
            overall_usage = total_usage / len(cores) if cores else 0.0

            return ServerMetrics(
                server_name=self.ssh_client.config.name,
                timestamp=time.time(),
                cores=sorted(cores, key=lambda c: c.core_id),
                overall_usage=overall_usage,
                connected=True,
            )

        except Exception as e:
            logger.error(
                f"{self.ssh_client.config.name}: Error collecting CPU metrics: {e}", exc_info=True
            )
            return ServerMetrics(
                server_name=self.ssh_client.config.name,
                timestamp=time.time(),
                cores=[],
                overall_usage=0.0,
                connected=False,
                error_message=str(e),
            )

    def _parse_proc_stat(self, output: str) -> dict[int, dict[str, int]]:
        """Parse /proc/stat output to extract CPU statistics.

        Args:
            output: Content of /proc/stat

        Returns:
            Dictionary mapping core ID to CPU time statistics
        """
        stats = {}

        for line in output.split("\n"):
            if not line.startswith("cpu"):
                continue

            if line.startswith("cpu "):
                # Skip the aggregate line
                continue

            parts = line.split()
            if len(parts) < 5:
                continue

            # Extract core number from "cpuN"
            core_str = parts[0][3:]
            if not core_str.isdigit():
                continue

            core_id = int(core_str)

            # Parse CPU times: user, nice, system, idle, iowait, irq, softirq, ...
            try:
                stats[core_id] = {
                    "user": int(parts[1]),
                    "nice": int(parts[2]),
                    "system": int(parts[3]),
                    "idle": int(parts[4]),
                    "iowait": int(parts[5]) if len(parts) > 5 else 0,
                    "irq": int(parts[6]) if len(parts) > 6 else 0,
                    "softirq": int(parts[7]) if len(parts) > 7 else 0,
                }
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing CPU stats for core {core_id}: {e}")
                continue

        return stats

    def _calculate_cpu_usage(self, prev: dict[str, int], curr: dict[str, int]) -> float:
        """Calculate CPU usage percentage between two readings.

        Args:
            prev: Previous CPU time statistics
            curr: Current CPU time statistics

        Returns:
            CPU usage percentage (0-100)
        """
        # Calculate total time differences
        prev_idle = prev["idle"] + prev.get("iowait", 0)
        curr_idle = curr["idle"] + curr.get("iowait", 0)

        prev_total = sum(prev.values())
        curr_total = sum(curr.values())

        # Calculate differences
        total_diff = curr_total - prev_total
        idle_diff = curr_idle - prev_idle

        # Calculate usage percentage
        if total_diff == 0:
            return 0.0

        usage = ((total_diff - idle_diff) / total_diff) * 100.0

        # Clamp to 0-100 range
        return max(0.0, min(100.0, usage))
