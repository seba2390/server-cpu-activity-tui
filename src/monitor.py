"""CPU monitoring logic for collecting and processing CPU metrics."""

import asyncio
import logging
import time
from dataclasses import dataclass

import asyncssh

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
class MemoryInfo:
    """Memory information."""

    total_mb: float
    used_mb: float
    free_mb: float
    available_mb: float
    usage_percent: float
    cached_mb: float = 0.0
    buffers_mb: float = 0.0


@dataclass
class ServerMetrics:
    """CPU metrics for a server."""

    server_name: str
    timestamp: float
    cores: list[CPUCore]
    overall_usage: float
    connected: bool
    memory: MemoryInfo | None = None
    error_message: str | None = None

    @property
    def core_count(self) -> int:
        """Get number of CPU cores."""
        return len(self.cores)


class CPUMonitor:
    """Monitors CPU usage on remote servers via SSH."""

    def __init__(self, ssh_client: SSHClient, poll_interval: float = 2.0, history_window: int = 60):
        """Initialize CPU monitor.

        Args:
            ssh_client: SSH client for server connection
            poll_interval: Interval between CPU polls in seconds
            history_window: Number of seconds to keep in history
        """
        self.ssh_client = ssh_client
        self.poll_interval = poll_interval
        self.history_window = history_window

        self._running = False
        self._task: asyncio.Task | None = None
        self._latest_metrics: ServerMetrics | None = None
        self._lock = asyncio.Lock()

        # For CPU usage calculation
        self._prev_stats: dict[int, dict[str, int]] | None = None

        # CPU history: list of (timestamp, overall_usage) tuples
        self._cpu_history: list[tuple[float, float]] = []

        logger.info(f"CPUMonitor initialized for server '{ssh_client.config.name}': poll_interval={poll_interval}s, history_window={history_window}s")

    async def start(self):
        """Start monitoring CPU metrics."""
        if self._running:
            logger.warning(f"{self.ssh_client.config.name}: Monitor already running, skipping start")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"{self.ssh_client.config.name}: CPU monitoring started (poll_interval={self.poll_interval}s)")

    async def stop(self):
        """Stop monitoring CPU metrics."""
        if not self._running:
            logger.warning(f"{self.ssh_client.config.name}: Monitor not running, skipping stop")
            return

        logger.info(f"{self.ssh_client.config.name}: Stopping CPU monitoring...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info(f"{self.ssh_client.config.name}: Monitor task cancelled successfully")

        logger.info(f"{self.ssh_client.config.name}: CPU monitoring stopped")

    async def get_metrics(self) -> ServerMetrics | None:
        """Get the latest CPU metrics.

        Returns:
            Latest server metrics, or None if not available
        """
        async with self._lock:
            return self._latest_metrics

    async def get_cpu_history(self) -> list[tuple[float, float]]:
        """Get CPU usage history.

        Returns:
            List of (timestamp, overall_usage) tuples
        """
        async with self._lock:
            return self._cpu_history.copy()

    async def _monitor_loop(self):
        """Main monitoring loop that periodically collects CPU data."""
        logger.info(f"{self.ssh_client.config.name}: Monitor loop started")
        loop_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self._running:
            try:
                loop_count += 1

                # Ensure SSH connection is active
                if not await self.ssh_client.ensure_connected():
                    consecutive_failures += 1
                    logger.warning(f"{self.ssh_client.config.name}: Not connected, creating disconnected metrics (loop {loop_count}, consecutive failures: {consecutive_failures}/{max_consecutive_failures})")
                    async with self._lock:
                        self._latest_metrics = ServerMetrics(
                            server_name=self.ssh_client.config.name,
                            timestamp=time.time(),
                            cores=[],
                            overall_usage=0.0,
                            connected=False,
                            error_message=self.ssh_client.status.error_message,
                        )

                    # Stop monitoring if too many consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"{self.ssh_client.config.name}: Maximum consecutive failures ({max_consecutive_failures}) reached, stopping monitor")
                        break

                    await asyncio.sleep(self.poll_interval)
                    continue

                # Reset failure counter on successful connection
                if consecutive_failures > 0:
                    logger.info(f"{self.ssh_client.config.name}: Connection recovered, resetting failure counter (was {consecutive_failures})")
                    consecutive_failures = 0

                # Collect CPU metrics
                logger.info(f"{self.ssh_client.config.name}: Collecting CPU metrics (loop {loop_count})")
                metrics = await self._collect_cpu_metrics()

                async with self._lock:
                    self._latest_metrics = metrics

                    # Add to history if connected
                    if metrics.connected:
                        current_time = time.time()
                        self._cpu_history.append((current_time, metrics.overall_usage))

                        # Trim history to keep only data within the window
                        # Use max() to handle clock skew - keep at least last entry
                        cutoff_time = current_time - self.history_window
                        before_trim = len(self._cpu_history)
                        self._cpu_history = [(t, u) for t, u in self._cpu_history if t >= cutoff_time]
                        # If clock skew cleared all history, keep at least the current entry
                        if not self._cpu_history:
                            self._cpu_history = [(current_time, metrics.overall_usage)]
                        after_trim = len(self._cpu_history)

                        if loop_count % 20 == 0:  # Log every 20 loops to avoid spam
                            logger.info(f"{self.ssh_client.config.name}: Metrics collected: cores={len(metrics.cores)}, "
                                      f"overall_usage={metrics.overall_usage:.1f}%, history_points={after_trim} (trimmed {before_trim-after_trim})")

            except asyncio.CancelledError:
                logger.info(f"{self.ssh_client.config.name}: Monitor loop cancelled")
                break
            except (asyncssh.Error, OSError, ValueError) as e:
                consecutive_failures += 1
                logger.error(
                    f"{self.ssh_client.config.name}: Error in monitoring loop (loop {loop_count}, consecutive failures: {consecutive_failures}/{max_consecutive_failures}): {e}", exc_info=True
                )
                # Stop monitoring if too many consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"{self.ssh_client.config.name}: Maximum consecutive failures ({max_consecutive_failures}) reached, stopping monitor")
                    break

            await asyncio.sleep(self.poll_interval)

        logger.info(f"{self.ssh_client.config.name}: Monitor loop exited after {loop_count} iterations")

    async def _collect_cpu_metrics(self) -> ServerMetrics:
        """Collect CPU metrics from the remote server.

        Returns:
            ServerMetrics with current CPU usage data
        """
        try:
            logger.info(f"{self.ssh_client.config.name}: Executing remote commands for CPU and memory data")

            # Read /proc/stat to get CPU usage
            cpu_output = await self.ssh_client.execute_command("cat /proc/stat")

            # Read /proc/meminfo to get memory usage
            mem_output = await self.ssh_client.execute_command("cat /proc/meminfo")

            if cpu_output is None:
                logger.warning(f"{self.ssh_client.config.name}: Failed to read CPU stats from remote server")
                return ServerMetrics(
                    server_name=self.ssh_client.config.name,
                    timestamp=time.time(),
                    cores=[],
                    overall_usage=0.0,
                    connected=False,
                    error_message="Failed to read CPU stats",
                )

            logger.info(f"{self.ssh_client.config.name}: Received CPU data, parsing /proc/stat...")
            # Parse /proc/stat output
            current_stats = self._parse_proc_stat(cpu_output)
            logger.info(f"{self.ssh_client.config.name}: Parsed {len(current_stats)} CPU cores from /proc/stat")

            # Parse memory info
            if mem_output:
                logger.info(f"{self.ssh_client.config.name}: Parsing memory info from /proc/meminfo...")
                memory_info = self._parse_meminfo(mem_output)
                if memory_info:
                    logger.info(f"{self.ssh_client.config.name}: Memory parsed: {memory_info.usage_percent:.1f}% used ({memory_info.used_mb/1024:.1f}GB/{memory_info.total_mb/1024:.1f}GB)")
            else:
                logger.warning(f"{self.ssh_client.config.name}: Failed to read memory info")
                memory_info = None

            # Calculate CPU usage based on difference from previous reading
            cores = []
            total_usage = 0.0

            if self._prev_stats is not None:
                logger.info(f"{self.ssh_client.config.name}: Calculating CPU usage deltas from previous stats")
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
                logger.info(f"{self.ssh_client.config.name}: First reading, initializing cores with 0% usage")
                cores.extend(CPUCore(core_id=core_id, usage_percent=0.0) for core_id in current_stats)

            # Store current stats for next calculation
            self._prev_stats = current_stats

            # Calculate overall usage
            overall_usage = total_usage / len(cores) if cores else 0.0

            logger.info(f"{self.ssh_client.config.name}: Metrics collected successfully: {len(cores)} cores, overall_usage={overall_usage:.1f}%")

            return ServerMetrics(
                server_name=self.ssh_client.config.name,
                timestamp=time.time(),
                cores=sorted(cores, key=lambda c: c.core_id),
                overall_usage=overall_usage,
                connected=True,
                memory=memory_info,
            )

        except (asyncssh.Error, OSError, ValueError, KeyError) as e:
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
        lines_processed = 0
        cores_found = 0

        for line in output.split("\n"):
            if not line.startswith("cpu"):
                continue

            lines_processed += 1

            if line.startswith("cpu "):
                # Skip the aggregate line
                continue

            parts = line.split()
            if len(parts) < 5:
                logger.warning(f"{self.ssh_client.config.name}: Skipping malformed CPU line: {line[:50]}")
                continue

            # Extract core number from "cpuN"
            core_str = parts[0][3:]
            if not core_str.isdigit():
                logger.warning(f"{self.ssh_client.config.name}: Invalid core identifier: {parts[0]}")
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
                cores_found += 1
            except (ValueError, IndexError) as e:
                logger.warning(f"{self.ssh_client.config.name}: Error parsing CPU stats for core {core_id}: {e}")
                continue

        logger.info(f"{self.ssh_client.config.name}: Parsed /proc/stat: {lines_processed} lines processed, {cores_found} cores found")
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

    def _parse_meminfo(self, output: str) -> MemoryInfo | None:
        """Parse /proc/meminfo output to extract memory statistics.

        Args:
            output: Content of /proc/meminfo

        Returns:
            MemoryInfo object with memory statistics, or None if parsing fails
        """
        try:
            mem_values = {}
            lines_processed = 0

            for line in output.split("\n"):
                if ":" not in line:
                    continue

                parts = line.split(":")
                if len(parts) != 2:
                    continue

                key = parts[0].strip()
                value_str = parts[1].strip().split()[0]  # Remove 'kB' unit

                try:
                    mem_values[key] = int(value_str)
                    lines_processed += 1
                except ValueError:
                    continue

            # Extract required values (all in kB, convert to MB)
            total_kb = mem_values.get("MemTotal", 0)
            free_kb = mem_values.get("MemFree", 0)
            available_kb = mem_values.get("MemAvailable", free_kb)  # Fallback to free if not available
            buffers_kb = mem_values.get("Buffers", 0)
            cached_kb = mem_values.get("Cached", 0)

            if total_kb == 0:
                logger.warning(f"{self.ssh_client.config.name}: MemTotal is 0, cannot calculate memory usage")
                return None

            # Convert to MB
            total_mb = total_kb / 1024.0
            free_mb = free_kb / 1024.0
            available_mb = available_kb / 1024.0
            buffers_mb = buffers_kb / 1024.0
            cached_mb = cached_kb / 1024.0

            used_mb = total_mb - available_mb
            usage_percent = (used_mb / total_mb * 100.0) if total_mb > 0 else 0.0

            logger.info(f"{self.ssh_client.config.name}: Parsed /proc/meminfo: {lines_processed} values extracted, "
                       f"total={total_mb:.0f}MB, used={used_mb:.0f}MB, usage={usage_percent:.1f}%")

            return MemoryInfo(
                total_mb=total_mb,
                used_mb=used_mb,
                free_mb=free_mb,
                available_mb=available_mb,
                usage_percent=usage_percent,
                cached_mb=cached_mb,
                buffers_mb=buffers_mb,
            )

        except Exception as e:
            logger.warning(f"{self.ssh_client.config.name}: Error parsing memory info: {e}")
            return None
