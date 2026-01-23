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
        logger.info(f"CPUMonitoringApp initialized with config_path: {config_path}")

    def load_config(self):
        """Load configuration from YAML file."""
        config_file = Path(self.config_path)

        logger.info(f"Loading configuration from: {config_file.absolute()}")

        if not config_file.exists():
            logger.error(f"Configuration file not found: {config_file}")
            sys.exit(1)

        try:
            with open(config_file, "r") as f:
                self.config = yaml.safe_load(f)

            logger.info(f"Configuration loaded successfully from {config_file}")

            # Validate required sections
            if "servers" not in self.config:
                logger.error("Configuration missing 'servers' section")
                sys.exit(1)

            if not self.config["servers"]:
                logger.error("No servers configured")
                sys.exit(1)

            server_count = len(self.config["servers"])
            logger.info(f"Configuration validated: {server_count} server(s) found")
            for i, server in enumerate(self.config["servers"], 1):
                logger.info(f"  Server {i}: {server.get('name', 'unnamed')} ({server.get('host', 'no-host')})")

        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            sys.exit(1)

    def initialize_components(self):
        """Initialize SSH clients, monitors, and UI widgets."""
        logger.info("Initializing application components...")

        # Get configuration values with defaults
        monitoring_config = self.config.get("monitoring", {})
        display_config = self.config.get("display", {})

        poll_interval = monitoring_config.get("poll_interval", 2.0)
        history_window = monitoring_config.get("history_window", 60)
        connection_timeout = monitoring_config.get("connection_timeout", 10)
        max_retries = monitoring_config.get("max_retries", 3)
        retry_delay = monitoring_config.get("retry_delay", 5)

        low_threshold = display_config.get("low_threshold", 30)
        medium_threshold = display_config.get("medium_threshold", 70)
        start_collapsed = display_config.get("start_collapsed", False)

        logger.info(f"Configuration parameters: poll_interval={poll_interval}s, history_window={history_window}s, ")
        logger.info(f"  connection_timeout={connection_timeout}s, max_retries={max_retries}, retry_delay={retry_delay}s")
        logger.info(f"  thresholds: low={low_threshold}%, medium={medium_threshold}%, start_collapsed={start_collapsed}")

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

                logger.info(f"Creating components for server: {srv_config.name} ({srv_config.host})")

                # Create SSH client
                ssh_client = SSHClient(
                    config=srv_config,
                    connection_timeout=connection_timeout,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )
                self.ssh_clients.append(ssh_client)
                logger.info(f"  SSHClient created for {srv_config.name}")

                # Create CPU monitor
                monitor = CPUMonitor(ssh_client=ssh_client, poll_interval=poll_interval, history_window=history_window)
                self.monitors.append(monitor)
                logger.info(f"  CPUMonitor created for {srv_config.name}")

                # Create UI widget
                widget = ServerWidget(
                    server_name=srv_config.name,
                    low_threshold=low_threshold,
                    medium_threshold=medium_threshold,
                    start_collapsed=start_collapsed,
                    history_window=history_window,
                )
                self.server_widgets.append(widget)
                logger.info(f"  ServerWidget created for {srv_config.name}")

                logger.info(f"All components initialized successfully for server: {srv_config.name}")

            except KeyError as e:
                logger.error(f"Server configuration missing required field: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error initializing server components: {e}")
                sys.exit(1)

        logger.info(f"Component initialization complete: {len(self.ssh_clients)} servers configured")

    async def start_monitoring(self):
        """Start all monitoring tasks."""
        logger.info(f"Starting monitoring for {len(self.ssh_clients)} servers in background...")

        # Start monitoring for all servers immediately - connections will happen in background
        logger.info("Starting CPU monitors for all servers...")
        for monitor in self.monitors:
            await monitor.start()
            logger.info(f"  Monitor started for: {monitor.ssh_client.config.name}")

        logger.info(f"All {len(self.monitors)} monitors started - connections will occur in background")

    async def stop_monitoring(self):
        """Stop all monitoring tasks."""
        logger.info("Stopping monitoring for all servers...")

        # Stop UI update task
        if self._ui_update_task:
            logger.info("Cancelling UI update task...")
            self._ui_update_task.cancel()
            try:
                await self._ui_update_task
            except asyncio.CancelledError:
                logger.info("UI update task cancelled successfully")
                pass

        # Stop all monitors
        logger.info(f"Stopping {len(self.monitors)} CPU monitors...")
        for monitor in self.monitors:
            server_name = monitor.ssh_client.config.name
            await monitor.stop()
            logger.info(f"  Monitor stopped for: {server_name}")

        # Disconnect all SSH clients
        logger.info(f"Disconnecting {len(self.ssh_clients)} SSH clients...")
        for ssh_client in self.ssh_clients:
            await ssh_client.disconnect()
            logger.info(f"  Disconnected from: {ssh_client.config.name}")

        logger.info("All monitoring stopped and connections closed")

    def save_config(self):
        """Save current configuration to YAML file."""
        logger.info(f"Saving configuration to: {self.config_path}")
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved successfully to {self.config_path}")
            logger.info(f"  Current server count: {len(self.config.get('servers', []))}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def delete_server(self, server_name: str):
        """Delete a server from the configuration and stop its monitoring.

        Args:
            server_name: Name of the server to delete
        """
        logger.info(f"Deleting server: {server_name}")

        # Find and remove the server from config
        initial_count = len(self.config["servers"])
        self.config["servers"] = [
            s for s in self.config["servers"] if s["name"] != server_name
        ]
        final_count = len(self.config["servers"])
        logger.info(f"  Removed from config: {initial_count} -> {final_count} servers")

        # Find index of the server to remove
        idx = None
        for i, client in enumerate(self.ssh_clients):
            if client.config.name == server_name:
                idx = i
                break

        if idx is not None:
            logger.info(f"  Found server at index {idx}, removing components...")
            # Stop and remove components
            monitor = self.monitors.pop(idx)
            ssh_client = self.ssh_clients.pop(idx)
            self.server_widgets.pop(idx)

            logger.info(f"  Components removed for '{server_name}', scheduling cleanup...")
            # Schedule async cleanup
            asyncio.create_task(self._cleanup_server(monitor, ssh_client))
        else:
            logger.warning(f"  Server '{server_name}' not found in active components (may have been already removed)")

        # Save updated config
        self.save_config()
        logger.info(f"Server deletion complete: {server_name}")

    async def _cleanup_server(self, monitor: CPUMonitor, ssh_client: SSHClient):
        """Clean up server resources asynchronously."""
        server_name = ssh_client.config.name
        logger.info(f"Cleaning up resources for server: {server_name}")
        await monitor.stop()
        logger.info(f"  Monitor stopped for: {server_name}")
        await ssh_client.disconnect()
        logger.info(f"  SSH client disconnected for: {server_name}")
        logger.info(f"Resource cleanup complete for: {server_name}")

    def add_server(self, server_config: dict):
        """Add a new server to the configuration and start monitoring.

        Args:
            server_config: Dictionary with name, host, username, key_path
        """
        server_name = server_config.get("name", "unnamed")
        logger.info(f"Adding new server: {server_name} ({server_config.get('host', 'no-host')})")

        # Add to config
        self.config["servers"].append(server_config)
        logger.info(f"  Server added to config, total servers: {len(self.config['servers'])}")

        # Get configuration values
        monitoring_config = self.config.get("monitoring", {})
        display_config = self.config.get("display", {})

        poll_interval = monitoring_config.get("poll_interval", 2.0)
        history_window = monitoring_config.get("history_window", 60)
        connection_timeout = monitoring_config.get("connection_timeout", 10)
        max_retries = monitoring_config.get("max_retries", 3)
        retry_delay = monitoring_config.get("retry_delay", 5)

        low_threshold = display_config.get("low_threshold", 30)
        medium_threshold = display_config.get("medium_threshold", 70)
        start_collapsed = display_config.get("start_collapsed", False)

        logger.info(f"  Creating components for {server_name}...")

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
        logger.info(f"  SSHClient created for {server_name}")

        monitor = CPUMonitor(ssh_client=ssh_client, poll_interval=poll_interval, history_window=history_window)
        self.monitors.append(monitor)
        logger.info(f"  CPUMonitor created for {server_name}")

        widget = ServerWidget(
            server_name=srv_config.name,
            low_threshold=low_threshold,
            medium_threshold=medium_threshold,
            start_collapsed=start_collapsed,
            history_window=history_window,
        )
        self.server_widgets.append(widget)
        logger.info(f"  ServerWidget created for {server_name}")

        # Add widget to UI
        if self.ui_app:
            self.ui_app.add_server_widget(widget)
            logger.info(f"  Widget added to UI for {server_name}")

        # Start monitoring
        logger.info(f"  Starting monitoring for {server_name}...")
        asyncio.create_task(self._start_server_monitoring(ssh_client, monitor))

        # Save config
        self.save_config()
        logger.info(f"Server addition complete: {server_name}")

    async def _start_server_monitoring(self, ssh_client: SSHClient, monitor: CPUMonitor):
        """Start monitoring for a new server."""
        server_name = ssh_client.config.name
        logger.info(f"Starting monitoring for new server: {server_name}")
        connection_result = await ssh_client.connect()
        if connection_result:
            logger.info(f"  Successfully connected to: {server_name}")
        else:
            logger.warning(f"  Failed to connect to: {server_name} (will retry automatically)")
        await monitor.start()
        logger.info(f"  Monitor started for: {server_name}")

    async def ui_update_loop(self):
        """Background task to update UI with latest metrics."""
        ui_refresh_interval = self.config.get("monitoring", {}).get("ui_refresh_interval", 0.5)
        logger.info(f"UI update loop started with refresh_interval={ui_refresh_interval}s")

        update_count = 0
        while self._running:
            try:
                # Collect metrics from all monitors
                for monitor, widget in zip(self.monitors, self.server_widgets):
                    metrics = await monitor.get_metrics()
                    if metrics:
                        widget.update_metrics(metrics)
                    else:
                        # No metrics yet - just refresh display to animate spinner
                        widget.refresh_display()

                    # Update history data
                    history_data = await monitor.get_cpu_history()
                    if history_data:
                        widget.update_history(history_data)

                # Update status bar timestamp
                if self.ui_app:
                    self.ui_app.update_metrics_timestamp()

                update_count += 1
                if update_count % 100 == 0:  # Log every 100 updates to avoid spam
                    logger.info(f"UI update loop: {update_count} updates completed")

                await asyncio.sleep(ui_refresh_interval)

            except asyncio.CancelledError:
                logger.info("UI update loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in UI update loop: {e}", exc_info=True)

    async def run_async(self):
        """Run the application asynchronously."""
        try:
            self._running = True
            logger.info("Application starting asynchronously...")

            # Start UI update task
            logger.info("Starting UI update task...")
            self._ui_update_task = asyncio.create_task(self.ui_update_loop())

            # Start monitoring in background (connections will happen while UI is running)
            logger.info("Starting background monitoring task...")
            monitoring_task = asyncio.create_task(self.start_monitoring())

            # Run the TUI app with callbacks for server management
            logger.info("Launching TUI application...")
            self.ui_app = MonitoringApp(
                server_widgets=self.server_widgets,
                on_delete_server=self.delete_server,
                on_add_server=self.add_server,
            )
            await self.ui_app.run_async()
            logger.info("TUI application exited")

            # Wait for monitoring task to complete if it's still running
            if not monitoring_task.done():
                logger.info("Waiting for monitoring initialization to complete...")
                await monitoring_task

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            self._running = False
            logger.info("Application shutting down...")
            await self.stop_monitoring()

    def run(self):
        """Run the application."""
        logger.info("Starting application run sequence...")
        try:
            asyncio.run(self.run_async())
            logger.info("Application run completed successfully")
        except KeyboardInterrupt:
            logger.info("Application terminated by user (KeyboardInterrupt)")
        except Exception as e:
            logger.error(f"Fatal error during application run: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point for the application."""
    logger.info("="*60)
    logger.info("CPU Monitoring TUI Application Starting")
    logger.info("="*60)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")

    try:
        app = CPUMonitoringApp()
        logger.info("CPUMonitoringApp instance created")

        app.load_config()
        logger.info("Configuration loaded successfully")

        app.initialize_components()
        logger.info("Components initialized successfully")

        logger.info("Launching application...")
        app.run()
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)

    logger.info("="*60)
    logger.info("Application shutdown complete")
    logger.info("="*60)


if __name__ == "__main__":
    main()
