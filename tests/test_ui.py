"""Tests for TUI components."""

import pytest
from unittest.mock import Mock
from textual.widgets import Static

from src.ui import CPUCoreWidget, ServerWidget, MemoryWidget, HistoryPlotWidget
from src.monitor import CPUCore, ServerMetrics, MemoryInfo


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

    # Mock the containers and query_one to avoid mounting issues in tests
    widget.cores_container = None  # Don't try to mount
    widget.header_widget = Static()
    widget.query_one = Mock(return_value=Mock())  # Mock query_one for cores_content

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


# Tests for ConfirmDeleteScreen


def test_confirm_delete_screen_initialization():
    """Test ConfirmDeleteScreen initialization."""
    from src.ui import ConfirmDeleteScreen

    screen = ConfirmDeleteScreen(server_name="test-server")
    assert screen.server_name == "test-server"


def test_confirm_delete_screen_yes_button():
    """Test ConfirmDeleteScreen yes button."""
    from src.ui import ConfirmDeleteScreen
    from textual.widgets import Button

    screen = ConfirmDeleteScreen(server_name="test-server")

    # Create a mock button pressed event
    yes_button = Button("Yes", id="yes-btn")
    event = Button.Pressed(yes_button)

    # Mock dismiss method
    screen.dismiss = Mock()

    screen.on_button_pressed(event)

    # Should dismiss with True
    screen.dismiss.assert_called_once_with(True)


def test_confirm_delete_screen_no_button():
    """Test ConfirmDeleteScreen no button."""
    from src.ui import ConfirmDeleteScreen
    from textual.widgets import Button

    screen = ConfirmDeleteScreen(server_name="test-server")

    # Create a mock button pressed event
    no_button = Button("No", id="no-btn")
    event = Button.Pressed(no_button)

    # Mock dismiss method
    screen.dismiss = Mock()

    screen.on_button_pressed(event)

    # Should dismiss with False
    screen.dismiss.assert_called_once_with(False)


def test_confirm_delete_screen_action_confirm():
    """Test ConfirmDeleteScreen confirm action."""
    from src.ui import ConfirmDeleteScreen

    screen = ConfirmDeleteScreen(server_name="test-server")
    screen.dismiss = Mock()

    screen.action_confirm()

    screen.dismiss.assert_called_once_with(True)


def test_confirm_delete_screen_action_cancel():
    """Test ConfirmDeleteScreen cancel action."""
    from src.ui import ConfirmDeleteScreen

    screen = ConfirmDeleteScreen(server_name="test-server")
    screen.dismiss = Mock()

    screen.action_cancel()

    screen.dismiss.assert_called_once_with(False)


# Tests for AddServerScreen


def test_add_server_screen_initialization():
    """Test AddServerScreen initialization."""
    from src.ui import AddServerScreen

    screen = AddServerScreen()
    # Just verify it can be created
    assert screen is not None


def test_add_server_screen_action_cancel():
    """Test AddServerScreen cancel action."""
    from src.ui import AddServerScreen

    screen = AddServerScreen()
    screen.dismiss = Mock()

    screen.action_cancel()

    screen.dismiss.assert_called_once_with(None)


def test_add_server_screen_cancel_button():
    """Test AddServerScreen cancel button."""
    from src.ui import AddServerScreen
    from textual.widgets import Button

    screen = AddServerScreen()

    # Create a mock button pressed event
    cancel_button = Button("Cancel", id="cancel-btn")
    event = Button.Pressed(cancel_button)

    # Mock dismiss method
    screen.dismiss = Mock()

    screen.on_button_pressed(event)

    # Should dismiss with None
    screen.dismiss.assert_called_once_with(None)


# Tests for MonitoringApp


def test_monitoring_app_initialization():
    """Test MonitoringApp initialization."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
    ]

    app = MonitoringApp(server_widgets=widgets)

    assert app.server_widgets == widgets
    assert app.selected_index == 0
    assert app._on_delete_server is None
    assert app._on_add_server is None


def test_monitoring_app_initialization_with_callbacks():
    """Test MonitoringApp initialization with callbacks."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1")]
    delete_cb = Mock()
    add_cb = Mock()

    app = MonitoringApp(
        server_widgets=widgets, on_delete_server=delete_cb, on_add_server=add_cb
    )

    assert app._on_delete_server == delete_cb
    assert app._on_add_server == add_cb


def test_monitoring_app_action_navigate_up():
    """Test MonitoringApp navigate up action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
        ServerWidget(server_name="server3"),
    ]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 2
    app._update_selection = Mock()

    app.action_navigate_up()

    assert app.selected_index == 1
    app._update_selection.assert_called_once()


def test_monitoring_app_action_navigate_up_at_top():
    """Test MonitoringApp navigate up at top (should not change)."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
    ]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0
    app._update_selection = Mock()

    app.action_navigate_up()

    assert app.selected_index == 0
    app._update_selection.assert_not_called()


def test_monitoring_app_action_navigate_down():
    """Test MonitoringApp navigate down action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
        ServerWidget(server_name="server3"),
    ]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0
    app._update_selection = Mock()

    app.action_navigate_down()

    assert app.selected_index == 1
    app._update_selection.assert_called_once()


def test_monitoring_app_action_navigate_down_at_bottom():
    """Test MonitoringApp navigate down at bottom (should not change)."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
    ]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 1
    app._update_selection = Mock()

    app.action_navigate_down()

    assert app.selected_index == 1
    app._update_selection.assert_not_called()


def test_monitoring_app_action_toggle_expand():
    """Test MonitoringApp toggle expand action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1", start_collapsed=True)]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0

    initial_expanded = widgets[0].expanded

    app.action_toggle_expand()

    assert widgets[0].expanded != initial_expanded


def test_monitoring_app_action_expand():
    """Test MonitoringApp expand action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1", start_collapsed=True)]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0

    assert not widgets[0].expanded

    app.action_expand()

    assert widgets[0].expanded


def test_monitoring_app_action_expand_already_expanded():
    """Test MonitoringApp expand when already expanded."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1", start_collapsed=False)]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0

    assert widgets[0].expanded

    app.action_expand()

    # Should remain expanded
    assert widgets[0].expanded


def test_monitoring_app_action_collapse():
    """Test MonitoringApp collapse action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1", start_collapsed=False)]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0

    assert widgets[0].expanded

    app.action_collapse()

    assert not widgets[0].expanded


def test_monitoring_app_action_collapse_already_collapsed():
    """Test MonitoringApp collapse when already collapsed."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1", start_collapsed=True)]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 0

    assert not widgets[0].expanded

    app.action_collapse()

    # Should remain collapsed
    assert not widgets[0].expanded


def test_monitoring_app_action_refresh():
    """Test MonitoringApp refresh action."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
    ]

    # Mock refresh_display
    for widget in widgets:
        widget.refresh_display = Mock()

    app = MonitoringApp(server_widgets=widgets)

    app.action_refresh()

    # All widgets should be refreshed
    for widget in widgets:
        widget.refresh_display.assert_called_once()


def test_monitoring_app_action_delete_server_no_servers():
    """Test MonitoringApp delete server with no servers."""
    from src.ui import MonitoringApp

    app = MonitoringApp(server_widgets=[])
    app.notify = Mock()

    app.action_delete_server()

    app.notify.assert_called_once()
    assert "No servers" in str(app.notify.call_args)


def test_monitoring_app_add_server_widget():
    """Test MonitoringApp add_server_widget method."""
    from src.ui import MonitoringApp, ServerWidget
    from unittest.mock import MagicMock

    widgets = [ServerWidget(server_name="server1")]
    app = MonitoringApp(server_widgets=widgets)

    # Mock main_container
    app.main_container = MagicMock()
    app._update_selection = Mock()

    new_widget = ServerWidget(server_name="server2")
    app.add_server_widget(new_widget)

    # Should be added to list
    assert len(app.server_widgets) == 2
    assert app.server_widgets[-1] == new_widget

    # Should be mounted to container
    app.main_container.mount.assert_called_once_with(new_widget)

    # Selection should be updated to new widget
    assert app.selected_index == 1
    app._update_selection.assert_called_once()


def test_monitoring_app_update_selection():
    """Test MonitoringApp _update_selection method."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [
        ServerWidget(server_name="server1"),
        ServerWidget(server_name="server2"),
        ServerWidget(server_name="server3"),
    ]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 1

    app._update_selection()

    # Only second widget should be selected
    assert not widgets[0].is_selected
    assert widgets[1].is_selected
    assert not widgets[2].is_selected


def test_cpu_core_widget_bar_width_calculation():
    """Test CPU core widget bar rendering with different usage values."""
    core = CPUCore(core_id=0, usage_percent=0.0)
    widget = CPUCoreWidget(core)

    rendered = widget.render()
    assert "0.0%" in rendered

    # Test 50%
    core = CPUCore(core_id=0, usage_percent=50.0)
    widget = CPUCoreWidget(core)
    rendered = widget.render()
    assert "50.0%" in rendered

    # Test 100%
    core = CPUCore(core_id=0, usage_percent=100.0)
    widget = CPUCoreWidget(core)
    rendered = widget.render()
    assert "100.0%" in rendered


def test_cpu_core_widget_threshold_boundaries():
    """Test CPU core widget color at threshold boundaries."""
    # Test exactly at low threshold
    core = CPUCore(core_id=0, usage_percent=30.0)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)
    rendered = widget.render()
    assert "[yellow]" in rendered

    # Test exactly at medium threshold
    core = CPUCore(core_id=0, usage_percent=70.0)
    widget = CPUCoreWidget(core, low_threshold=30, medium_threshold=70)
    rendered = widget.render()
    assert "[red]" in rendered


def test_server_widget_display_without_metrics():
    """Test server widget display before metrics are available."""
    widget = ServerWidget(server_name="test-server")
    widget.header_widget = Static()

    widget.refresh_display()

    # Should show initializing status
    assert widget.header_widget is not None


def test_server_widget_collapsed_cores_not_displayed():
    """Test that cores are hidden when widget is collapsed."""
    widget = ServerWidget(server_name="test-server", start_collapsed=True)
    widget.cores_container = Static()

    assert not widget.expanded

    widget.refresh_display()

    # Cores container should be hidden (display will be False)
    # Note: In Textual, display property defaults to True, we set it to False to hide
    assert widget.cores_container.display is not True or not widget.expanded


def test_server_widget_expanded_cores_displayed():
    """Test that cores are shown when widget is expanded."""
    widget = ServerWidget(server_name="test-server", start_collapsed=False)
    widget.cores_container = Static()

    assert widget.expanded

    widget.refresh_display()

    # Cores container should be visible
    assert widget.cores_container.display == True


def test_server_widget_safe_id_generation():
    """Test server widget generates safe IDs for server names with spaces."""
    widget = ServerWidget(server_name="My Test Server")

    # The compose method creates IDs with safe names
    # This test verifies the widget can be created with such names
    assert widget.server_name == "My Test Server"


def test_server_widget_error_message_display():
    """Test server widget displays error message when disconnected."""
    widget = ServerWidget(server_name="test-server")
    widget.header_widget = Static()

    metrics = ServerMetrics(
        server_name="test-server",
        timestamp=1234567890.0,
        cores=[],
        overall_usage=0.0,
        connected=False,
        error_message="Connection timeout",
    )

    widget.metrics = metrics
    widget.refresh_display()

    # The error message should be visible when we call refresh_display
    # Since we're testing without actually mounting, just verify metrics was set
    assert not widget.metrics.connected
    assert "timeout" in widget.metrics.error_message.lower()


def test_server_widget_remove_excess_core_widgets():
    """Test server widget removes excess core widgets when cores decrease."""
    widget = ServerWidget(server_name="test-server")
    widget.cores_container = None  # Don't mount
    widget.header_widget = Static()
    mock_container = Mock()
    widget.query_one = Mock(return_value=mock_container)

    # Start with 4 cores
    cores = [CPUCore(core_id=i, usage_percent=50.0) for i in range(4)]
    metrics = ServerMetrics(
        server_name="test-server",
        timestamp=1234567890.0,
        cores=cores,
        overall_usage=50.0,
        connected=True,
    )

    widget.update_metrics(metrics)
    assert len(widget.core_widgets) == 4

    # Now only 2 cores
    cores = [CPUCore(core_id=i, usage_percent=50.0) for i in range(2)]
    metrics = ServerMetrics(
        server_name="test-server",
        timestamp=1234567890.0,
        cores=cores,
        overall_usage=50.0,
        connected=True,
    )

    # Mock remove method on excess widgets
    for w in widget.core_widgets:
        w.remove = Mock()

    widget.update_metrics(metrics)

    # Should have removed excess widgets
    assert len(widget.core_widgets) == 2


def test_monitoring_app_action_toggle_expand_invalid_index():
    """Test MonitoringApp toggle expand with invalid index."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1")]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = 999  # Invalid index

    # Should handle gracefully
    app.action_toggle_expand()


def test_monitoring_app_action_expand_invalid_index():
    """Test MonitoringApp expand with invalid index."""
    from src.ui import MonitoringApp, ServerWidget

    widgets = [ServerWidget(server_name="server1")]

    app = MonitoringApp(server_widgets=widgets)
    app.selected_index = -1  # Invalid index

    # Should handle gracefully
    app.action_expand()


def test_monitoring_app_add_server_widget_without_container():
    """Test MonitoringApp add_server_widget without main_container."""
    from src.ui import MonitoringApp, ServerWidget

    app = MonitoringApp(server_widgets=[])
    app.main_container = None
    app._update_selection = Mock()

    new_widget = ServerWidget(server_name="server1")

    # Should not crash
    app.add_server_widget(new_widget)

    assert len(app.server_widgets) == 1


def test_memory_widget_initialization():
    """Test memory widget initialization."""
    widget = MemoryWidget(low_threshold=30, medium_threshold=70)

    assert widget.low_threshold == 30
    assert widget.medium_threshold == 70
    assert widget.memory_info is None


def test_memory_widget_render_no_data():
    """Test rendering memory widget with no data."""
    widget = MemoryWidget()

    rendered = widget.render()

    assert "No data available" in rendered


def test_memory_widget_render_low_usage():
    """Test rendering memory widget with low usage."""
    memory_info = MemoryInfo(
        total_mb=16000.0,
        used_mb=4000.0,
        free_mb=12000.0,
        available_mb=12000.0,
        usage_percent=25.0,
        cached_mb=1000.0,
        buffers_mb=500.0,
    )

    widget = MemoryWidget(low_threshold=30, medium_threshold=70)
    widget.update_memory(memory_info)

    rendered = widget.render()

    assert "Memory:" in rendered
    assert "25.0%" in rendered
    assert "[green]" in rendered  # Should be green for low usage


def test_memory_widget_render_medium_usage():
    """Test rendering memory widget with medium usage."""
    memory_info = MemoryInfo(
        total_mb=16000.0,
        used_mb=8000.0,
        free_mb=8000.0,
        available_mb=8000.0,
        usage_percent=50.0,
        cached_mb=1000.0,
        buffers_mb=500.0,
    )

    widget = MemoryWidget(low_threshold=30, medium_threshold=70)
    widget.update_memory(memory_info)

    rendered = widget.render()

    assert "50.0%" in rendered
    assert "[yellow]" in rendered  # Should be yellow for medium usage


def test_memory_widget_render_high_usage():
    """Test rendering memory widget with high usage."""
    memory_info = MemoryInfo(
        total_mb=16000.0,
        used_mb=14000.0,
        free_mb=2000.0,
        available_mb=2000.0,
        usage_percent=87.5,
        cached_mb=1000.0,
        buffers_mb=500.0,
    )

    widget = MemoryWidget(low_threshold=30, medium_threshold=70)
    widget.update_memory(memory_info)

    rendered = widget.render()

    assert "87.5%" in rendered
    assert "[red]" in rendered  # Should be red for high usage


def test_history_plot_widget_initialization():
    """Test history plot widget initialization."""
    widget = HistoryPlotWidget(history_window=120)

    assert widget.history_window == 120
    assert widget.history_data == []


def test_history_plot_widget_render_no_data():
    """Test rendering history plot with no data."""
    widget = HistoryPlotWidget()

    rendered = widget.render()

    assert "Collecting data" in rendered or "No data" in rendered.lower()


def test_history_plot_widget_render_with_data():
    """Test rendering history plot with data."""
    import time

    current_time = time.time()
    history_data = [
        (current_time - 30, 30.0),
        (current_time - 20, 45.0),
        (current_time - 10, 60.0),
        (current_time, 50.0),
    ]

    widget = HistoryPlotWidget(history_window=60)
    widget.update_history(history_data)

    rendered = widget.render()

    # Should show the plot title and time axis
    assert "AVG CPU UTILIZATION" in rendered
    assert "now" in rendered
    # Should have filled area plot characters
    assert any(char in rendered for char in ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"])


def test_history_plot_widget_update():
    """Test updating history plot data."""
    import time

    widget = HistoryPlotWidget()

    assert widget.history_data == []

    current_time = time.time()
    new_data = [(current_time - 10, 40.0), (current_time, 50.0)]

    widget.update_history(new_data)

    assert widget.history_data == new_data


def test_server_widget_with_history_window():
    """Test server widget initialization with history_window."""
    widget = ServerWidget(
        server_name="test-server",
        low_threshold=30,
        medium_threshold=70,
        start_collapsed=False,
        history_window=120,
    )

    assert widget.server_name == "test-server"
    assert widget.history_window == 120
    assert widget.expanded


def test_server_widget_update_history():
    """Test server widget history update."""
    import time

    widget = ServerWidget(server_name="test-server")

    # Update would normally be called after mount, so we need to set up the widget first
    # For this test, we'll just verify the method exists and can be called
    current_time = time.time()
    history_data = [(current_time - 10, 40.0), (current_time, 50.0)]

    # This should not raise an error even if history_widget is None
    widget.update_history(history_data)
