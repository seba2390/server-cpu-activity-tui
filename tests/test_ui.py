"""Tests for TUI components."""

import pytest
from textual.widgets import Static

from src.ui import CPUCoreWidget, ServerWidget
from src.monitor import CPUCore, ServerMetrics


def test_cpu_core_widget_initialization():
    """Test CPU core widget initialization."""
    core = CPUCore(core_id=0, usage_percent=45.5)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)

    assert widget.core == core
    assert widget.low_threshold == 30
    assert widget.medium_threshold == 70
    assert widget.usage_percent == 45.5


def test_cpu_core_widget_render_low_usage():
    """Test rendering with low CPU usage."""
    core = CPUCore(core_id=0, usage_percent=25.0)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)

    rendered = widget.render()

    assert "Core  0:" in rendered
    assert "25.0%" in rendered
    assert "[green]" in rendered  # Should be green for low usage


def test_cpu_core_widget_render_medium_usage():
    """Test rendering with medium CPU usage."""
    core = CPUCore(core_id=1, usage_percent=50.0)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)

    rendered = widget.render()

    assert "Core  1:" in rendered
    assert "50.0%" in rendered
    assert "[yellow]" in rendered  # Should be yellow for medium usage


def test_cpu_core_widget_render_high_usage():
    """Test rendering with high CPU usage."""
    core = CPUCore(core_id=2, usage_percent=85.0)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)

    rendered = widget.render()

    assert "Core  2:" in rendered
    assert "85.0%" in rendered
    assert "[red]" in rendered  # Should be red for high usage


def test_cpu_core_widget_update():
    """Test updating CPU core data."""
    core1 = CPUCore(core_id=0, usage_percent=25.0)
    core2 = CPUCore(core_id=0, usage_percent=75.0)

    widget = CPUCoreWidget(core1)
    assert widget.usage_percent == 25.0

    widget.update_core(core2)
    assert widget.usage_percent == 75.0
    assert widget.core == core2


def test_server_widget_initialization():
    """Test server widget initialization."""
    widget = ServerWidget(
        server_name="test-server", low_threshold=30, medium_threshold=70, start_collapsed=True
    )

    assert widget.server_name == "test-server"
    assert widget.low_threshold == 30
    assert widget.medium_threshold == 70
    assert not widget.expanded  # start_collapsed=True means not expanded
    assert not widget.is_selected


def test_server_widget_toggle_expanded():
    """Test toggling server widget expansion."""
    widget = ServerWidget(server_name="test-server", start_collapsed=False)

    assert widget.expanded

    widget.toggle_expanded()
    assert not widget.expanded

    widget.toggle_expanded()
    assert widget.expanded


def test_server_widget_set_selected():
    """Test setting server widget selection state."""
    widget = ServerWidget(server_name="test-server")

    assert not widget.is_selected

    widget.set_selected(True)
    assert widget.is_selected

    widget.set_selected(False)
    assert not widget.is_selected


def test_server_widget_update_metrics():
    """Test updating server metrics."""
    widget = ServerWidget(server_name="test-server")

    # Create test metrics
    cores = [
        CPUCore(core_id=0, usage_percent=25.0),
        CPUCore(core_id=1, usage_percent=50.0),
        CPUCore(core_id=2, usage_percent=75.0),
    ]

    metrics = ServerMetrics(
        server_name="test-server",
        timestamp=1234567890.0,
        cores=cores,
        overall_usage=50.0,
        connected=True,
    )

    # Mock the containers to avoid mounting issues in tests
    widget.cores_container = None  # Don't try to mount
    widget.header_widget = Static()

    widget.update_metrics(metrics)

    assert widget.metrics == metrics


def test_server_widget_update_metrics_disconnected():
    """Test updating with disconnected server metrics."""
    widget = ServerWidget(server_name="test-server")

    metrics = ServerMetrics(
        server_name="test-server",
        timestamp=1234567890.0,
        cores=[],
        overall_usage=0.0,
        connected=False,
        error_message="Connection timeout",
    )

    widget.header_widget = Static()
    widget.cores_container = None

    widget.update_metrics(metrics)

    assert widget.metrics == metrics
    assert not widget.metrics.connected


def test_server_metrics_core_count():
    """Test ServerMetrics core_count property."""
    cores = [
        CPUCore(core_id=0, usage_percent=25.0),
        CPUCore(core_id=1, usage_percent=50.0),
    ]

    metrics = ServerMetrics(
        server_name="test", timestamp=1234567890.0, cores=cores, overall_usage=37.5, connected=True
    )

    assert metrics.core_count == 2
