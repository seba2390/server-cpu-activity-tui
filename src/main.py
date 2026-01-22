"""Main application entry point for CPU monitoring TUI."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

from .ssh_client import SSHClient, ServerConfig
from .monitor import CPUMonitor
from .ui import MonitoringApp, ServerWidget

# Configure logging - only to file, not to terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("cpu_monitor.log")],
)

logger = logging.getLogger(__name__)


class CPUMonitoringApp:
    """Main application coordinating SSH, monitoring, and UI."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the monitoring application.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: dict = {}
        self.ssh_clients: list[SSHClient] = []
        self.monitors: list[CPUMonitor] = []
        self.server_widgets: list[ServerWidget] = []
        self.ui_app: Optional[MonitoringApp] = None
        self._ui_update_task: Optional[asyncio.Task] = None
        self._running = False

    def load_config(self):
        """Load configuration from YAML file."""
        config_file = Path(self.config_path)

        if not config_file.exists():
            logger.error(f"Configuration file not found: {config_file}")
            sys.exit(1)

        try:
            with open(config_file, "r") as f:
                self.config = yaml.safe_load(f)

            logger.info(f"Loaded configuration from {config_file}")

            # Validate required sections
            if "servers" not in self.config:
                logger.error("Configuration missing 'servers' section")
                sys.exit(1)

            if not self.config["servers"]:
                logger.error("No servers configured")
                sys.exit(1)

        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            sys.exit(1)

    def initialize_components(self):
        """Initialize SSH clients, monitors, and UI widgets."""
        # Get configuration values with defaults
        monitoring_config = self.config.get("monitoring", {})
        display_config = self.config.get("display", {})

        poll_interval = monitoring_config.get("poll_interval", 2.0)
        connection_timeout = monitoring_config.get("connection_timeout", 10)
        max_retries = monitoring_config.get("max_retries", 3)
        retry_delay = monitoring_config.get("retry_delay", 5)

        low_threshold = display_config.get("low_threshold", 30)
        medium_threshold = display_config.get("medium_threshold", 70)
        start_collapsed = display_config.get("start_collapsed", False)

        # Create components for each server
        for server_config in self.config["servers"]:
            try:
                # Create server configuration
                srv_config = ServerConfig(
                    name=server_config["name"],
                    host=server_config["host"],
                    username=server_config["username"],
                    key_path=server_config["key_path"],
                )

                # Create SSH client
                ssh_client = SSHClient(
                    config=srv_config,
                    connection_timeout=connection_timeout,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )
                self.ssh_clients.append(ssh_client)

                # Create CPU monitor
                monitor = CPUMonitor(ssh_client=ssh_client, poll_interval=poll_interval)
                self.monitors.append(monitor)

                # Create UI widget
                widget = ServerWidget(
                    server_name=srv_config.name,
                    low_threshold=low_threshold,
                    medium_threshold=medium_threshold,
                    start_collapsed=start_collapsed,
                )
                self.server_widgets.append(widget)

                logger.info(f"Initialized components for server: {srv_config.name}")

            except KeyError as e:
                logger.error(f"Server configuration missing required field: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error initializing server components: {e}")
                sys.exit(1)

    async def start_monitoring(self):
        """Start all monitoring tasks."""
        logger.info("Starting monitoring for all servers...")

        # Connect to all servers and start monitoring
        connect_tasks = []
        for ssh_client, monitor in zip(self.ssh_clients, self.monitors):
            connect_tasks.append(ssh_client.connect())

        # Connect in parallel
        results = await asyncio.gather(*connect_tasks, return_exceptions=True)

        # Start monitoring for all servers (including those that failed to connect)
        for monitor in self.monitors:
            await monitor.start()

        # Log connection results
        for ssh_client, result in zip(self.ssh_clients, results):
            if isinstance(result, Exception):
                logger.error(f"{ssh_client.config.name}: Connection failed: {result}")
            elif result:
                logger.info(f"{ssh_client.config.name}: Connected and monitoring")
            else:
                logger.warning(f"{ssh_client.config.name}: Failed to connect")

    async def stop_monitoring(self):
        """Stop all monitoring tasks."""
        logger.info("Stopping monitoring...")

        # Stop UI update task
        if self._ui_update_task:
            self._ui_update_task.cancel()
            try:
                await self._ui_update_task
            except asyncio.CancelledError:
                pass

        # Stop all monitors
        for monitor in self.monitors:
            await monitor.stop()

        # Disconnect all SSH clients
        for ssh_client in self.ssh_clients:
            await ssh_client.disconnect()

        logger.info("Monitoring stopped")

    def save_config(self):
        """Save current configuration to YAML file."""
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def delete_server(self, server_name: str):
        """Delete a server from the configuration and stop its monitoring.

        Args:
            server_name: Name of the server to delete
        """
        # Find and remove the server from config
        self.config["servers"] = [
            s for s in self.config["servers"] if s["name"] != server_name
        ]

        # Find index of the server to remove
        idx = None
        for i, client in enumerate(self.ssh_clients):
            if client.config.name == server_name:
                idx = i
                break

        if idx is not None:
            # Stop and remove components
            monitor = self.monitors.pop(idx)
            ssh_client = self.ssh_clients.pop(idx)
            self.server_widgets.pop(idx)

            # Schedule async cleanup
            asyncio.create_task(self._cleanup_server(monitor, ssh_client))

        # Save updated config
        self.save_config()
        logger.info(f"Deleted server: {server_name}")

    async def _cleanup_server(self, monitor: CPUMonitor, ssh_client: SSHClient):
        """Clean up server resources asynchronously."""
        await monitor.stop()
        await ssh_client.disconnect()

    def add_server(self, server_config: dict):
        """Add a new server to the configuration and start monitoring.

        Args:
            server_config: Dictionary with name, host, username, key_path
        """
        # Add to config
        self.config["servers"].append(server_config)

        # Get configuration values
        monitoring_config = self.config.get("monitoring", {})
        display_config = self.config.get("display", {})

        poll_interval = monitoring_config.get("poll_interval", 2.0)
        connection_timeout = monitoring_config.get("connection_timeout", 10)
        max_retries = monitoring_config.get("max_retries", 3)
        retry_delay = monitoring_config.get("retry_delay", 5)

        low_threshold = display_config.get("low_threshold", 30)
        medium_threshold = display_config.get("medium_threshold", 70)
        start_collapsed = display_config.get("start_collapsed", False)

        # Create components
        srv_config = ServerConfig(
            name=server_config["name"],
            host=server_config["host"],
            username=server_config["username"],
            key_path=server_config["key_path"],
        )

        ssh_client = SSHClient(
            config=srv_config,
            connection_timeout=connection_timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.ssh_clients.append(ssh_client)

        monitor = CPUMonitor(ssh_client=ssh_client, poll_interval=poll_interval)
        self.monitors.append(monitor)

        widget = ServerWidget(
            server_name=srv_config.name,
            low_threshold=low_threshold,
            medium_threshold=medium_threshold,
            start_collapsed=start_collapsed,
        )
        self.server_widgets.append(widget)

        # Add widget to UI
        if self.ui_app:
            self.ui_app.add_server_widget(widget)

        # Start monitoring
        asyncio.create_task(self._start_server_monitoring(ssh_client, monitor))

        # Save config
        self.save_config()
        logger.info(f"Added server: {srv_config.name}")

    async def _start_server_monitoring(self, ssh_client: SSHClient, monitor: CPUMonitor):
        """Start monitoring for a new server."""
        await ssh_client.connect()
        await monitor.start()

    async def ui_update_loop(self):
        """Background task to update UI with latest metrics."""
        ui_refresh_interval = self.config.get("monitoring", {}).get("ui_refresh_interval", 0.5)

        while self._running:
            try:
                # Collect metrics from all monitors
                for monitor, widget in zip(self.monitors, self.server_widgets):
                    metrics = await monitor.get_metrics()
                    if metrics:
                        widget.update_metrics(metrics)

                await asyncio.sleep(ui_refresh_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in UI update loop: {e}", exc_info=True)

    async def run_async(self):
        """Run the application asynchronously."""
        try:
            self._running = True

            # Start monitoring
            await self.start_monitoring()

            # Start UI update task
            self._ui_update_task = asyncio.create_task(self.ui_update_loop())

            # Run the TUI app with callbacks for server management
            self.ui_app = MonitoringApp(
                server_widgets=self.server_widgets,
                on_delete_server=self.delete_server,
                on_add_server=self.add_server,
            )
            await self.ui_app.run_async()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            self._running = False
            await self.stop_monitoring()

    def run(self):
        """Run the application."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Application terminated by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point for the application."""
    logger.info("=" * 60)
    logger.info("CPU Monitoring TUI Application Starting")
    logger.info("=" * 60)

    app = CPUMonitoringApp()
    app.load_config()
    app.initialize_components()
    app.run()

    logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()
