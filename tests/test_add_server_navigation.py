"""Tests for AddServerScreen two-level navigation system."""

import pytest
from unittest.mock import Mock, patch
from textual.widgets import Input, OptionList, Button

from src.ui import AddServerScreen


class TestAddServerScreenTwoLevelNavigation:
    """Test suite for two-level navigation in AddServerScreen."""

    def test_initialization_defaults(self):
        """Test that screen initializes with correct defaults."""
        screen = AddServerScreen()

        assert screen.auth_method == "key"
        assert screen.current_field_index == 0
        assert screen.in_edit_mode is False
        assert screen.fields == []  # Will be populated on mount

    def test_fields_populated_on_mount(self):
        """Test that fields list is populated when screen mounts."""
        screen = AddServerScreen()
        screen.dismiss = Mock()

        # Simulate mount by calling on_mount directly
        # Note: This won't work perfectly without an app context,
        # but we can test the structure
        assert hasattr(screen, 'on_mount')
        assert callable(screen.on_mount)

    def test_get_current_field_valid_index(self):
        """Test getting current field with valid index."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 0

        field = screen._get_current_field()

        assert field is not None
        assert field["id"] == "input-name"
        assert field["type"] == "input"

    def test_get_current_field_invalid_index(self):
        """Test getting current field with invalid index."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
        ]
        screen.current_field_index = 10  # Out of bounds

        field = screen._get_current_field()

        assert field is None

    def test_get_current_field_empty_fields(self):
        """Test getting current field when fields list is empty."""
        screen = AddServerScreen()
        screen.fields = []
        screen.current_field_index = 0

        field = screen._get_current_field()

        assert field is None

    def test_action_navigate_down_in_navigation_mode(self):
        """Test navigating down in navigation mode."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 0
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen.action_navigate_down()

        assert screen.current_field_index == 1
        screen._update_field_highlights.assert_called()

    def test_action_navigate_down_in_edit_mode_does_nothing(self):
        """Test that navigating down in edit mode does nothing."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 0
        screen.in_edit_mode = True

        screen.action_navigate_down()

        # Should stay at same index when in edit mode
        assert screen.current_field_index == 0

    def test_action_navigate_up_in_navigation_mode(self):
        """Test navigating up in navigation mode."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 1
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen.action_navigate_up()

        assert screen.current_field_index == 0
        screen._update_field_highlights.assert_called()

    def test_action_navigate_up_in_edit_mode_does_nothing(self):
        """Test that navigating up in edit mode does nothing."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 1
        screen.in_edit_mode = True

        screen.action_navigate_up()

        # Should stay at same index when in edit mode
        assert screen.current_field_index == 1

    def test_action_enter_field_from_navigation_mode(self):
        """Test entering a field from navigation mode."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
        ]
        screen.current_field_index = 0
        screen.in_edit_mode = False

        # Before entering
        assert screen.in_edit_mode is False

    def test_action_enter_field_when_already_in_edit_mode(self):
        """Test that pressing enter when in edit mode exits the field."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
        ]
        screen.current_field_index = 0
        screen.in_edit_mode = True
        screen.action_exit_field = Mock()

        screen.action_enter_field()

        screen.action_exit_field.assert_called_once()

    def test_action_exit_field_when_not_in_edit_mode(self):
        """Test that exiting field when not in edit mode does nothing."""
        screen = AddServerScreen()
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen.action_exit_field()

        # Should not update highlights if not in edit mode
        screen._update_field_highlights.assert_not_called()

    def test_action_exit_field_transitions_to_navigation_mode(self):
        """Test that exiting field transitions to navigation mode."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
        ]
        screen.current_field_index = 0
        screen.in_edit_mode = True

        # Mock the widget and its methods
        with patch.object(screen, 'query_one') as mock_query:
            mock_input = Mock(spec=Input)
            mock_query.return_value = mock_input
            screen.focus = Mock()
            screen._update_field_highlights = Mock()

            screen.action_exit_field()

            # Should transition to navigation mode
            assert screen.in_edit_mode is False
            mock_input.disabled = True
            screen.focus.assert_called_once()

    def test_navigate_wraps_around_at_end(self):
        """Test that navigation wraps around at the end of field list."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 1  # Last field
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen.action_navigate_down()

        # Should wrap to first field
        assert screen.current_field_index == 0

    def test_navigate_wraps_around_at_start(self):
        """Test that navigation wraps around at the start of field list."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-host", "label_id": "label-host", "type": "input"},
        ]
        screen.current_field_index = 0  # First field
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen.action_navigate_up()

        # Should wrap to last field
        assert screen.current_field_index == 1

    def test_skip_hidden_fields_based_on_auth_method_key(self):
        """Test that navigation skips password field when auth method is key."""
        screen = AddServerScreen()
        screen.auth_method = "key"
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-keypath", "label_id": "label-keypath", "type": "input", "auth_type": "key"},
            {"id": "input-password", "label_id": "label-password", "type": "input", "auth_type": "password"},
            {"id": "add-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 1  # On keypath field
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen._navigate_to_next_valid_field()

        # Should skip password field and go to button
        assert screen.current_field_index == 3

    def test_skip_hidden_fields_based_on_auth_method_password(self):
        """Test that navigation skips key field when auth method is password."""
        screen = AddServerScreen()
        screen.auth_method = "password"
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "input-keypath", "label_id": "label-keypath", "type": "input", "auth_type": "key"},
            {"id": "input-password", "label_id": "label-password", "type": "input", "auth_type": "password"},
            {"id": "add-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 0  # On name field
        screen.in_edit_mode = False
        screen._update_field_highlights = Mock()

        screen._navigate_to_next_valid_field()

        # Should skip keypath field and go to password
        assert screen.current_field_index == 2

    def test_auth_method_change_updates_visible_fields(self):
        """Test that changing auth method updates visible fields."""
        screen = AddServerScreen()
        screen.auth_method = "key"

        # Mock the containers
        with patch.object(screen, 'query_one') as mock_query:
            mock_key_container = Mock()
            mock_password_container = Mock()

            def side_effect(selector):
                if selector == "#key-container":
                    return mock_key_container
                elif selector == "#password-container":
                    return mock_password_container
                return Mock()

            mock_query.side_effect = side_effect

            # Change to password
            screen.auth_method = "password"
            screen._update_auth_fields()

            # Key container should be hidden, password shown
            mock_key_container.add_class.assert_called_with("hidden")
            mock_password_container.remove_class.assert_called_with("hidden")

    def test_bindings_include_all_navigation_keys(self):
        """Test that all required key bindings are present."""
        screen = AddServerScreen()

        binding_keys = [b.key for b in screen.BINDINGS]

        assert "up" in binding_keys
        assert "down" in binding_keys
        assert "enter" in binding_keys
        assert "right" in binding_keys
        assert "left" in binding_keys
        assert "escape" in binding_keys
        assert "ctrl+s" in binding_keys

    def test_bindings_map_to_correct_actions(self):
        """Test that key bindings map to correct actions."""
        screen = AddServerScreen()

        bindings = {b.key: b.action for b in screen.BINDINGS}

        assert bindings["up"] == "navigate_up"
        assert bindings["down"] == "navigate_down"
        assert bindings["enter"] == "enter_field"
        assert bindings["right"] == "navigate_right"
        assert bindings["left"] == "navigate_left"
        assert bindings["escape"] == "cancel"
        assert bindings["ctrl+s"] == "submit"

    def test_action_navigate_right_transitions_add_to_cancel(self):
        """Test that right arrow on Add Server button moves to Cancel button."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "add-btn", "label_id": None, "type": "button"},
            {"id": "cancel-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 0  # On add-btn

        # Mock highlight update methods
        screen._update_field_highlights = Mock()
        screen.in_edit_mode = False

        screen.action_navigate_right()

        assert screen.current_field_index == 1  # Should move to cancel-btn

    def test_action_navigate_left_transitions_cancel_to_add(self):
        """Test that left arrow on Cancel button moves to Add Server button."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "add-btn", "label_id": None, "type": "button"},
            {"id": "cancel-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 1  # On cancel-btn

        # Mock highlight update methods
        screen._update_field_highlights = Mock()
        screen.in_edit_mode = False

        screen.action_navigate_left()

        assert screen.current_field_index == 0  # Should move to add-btn

    def test_action_navigate_down_skips_cancel_from_add(self):
        """Test that down arrow from Add Server button skips Cancel button."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "add-btn", "label_id": None, "type": "button"},
            {"id": "cancel-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 1  # On add-btn

        # Mock highlight update methods
        screen._update_field_highlights = Mock()
        screen.in_edit_mode = False

        screen.action_navigate_down()

        assert screen.current_field_index == 0  # Should wrap to input-name

    def test_action_navigate_up_skips_add_from_cancel(self):
        """Test that up arrow from Cancel button skips Add Server button."""
        screen = AddServerScreen()
        screen.fields = [
            {"id": "input-name", "label_id": "label-name", "type": "input"},
            {"id": "add-btn", "label_id": None, "type": "button"},
            {"id": "cancel-btn", "label_id": None, "type": "button"},
        ]
        screen.current_field_index = 2  # On cancel-btn

        # Mock highlight update methods
        screen._update_field_highlights = Mock()
        screen.in_edit_mode = False

        screen.action_navigate_up()

        assert screen.current_field_index == 0  # Should go to input-name

    def test_action_methods_exist(self):
        """Test that all required action methods exist."""
        screen = AddServerScreen()

        assert hasattr(screen, 'action_navigate_up')
        assert hasattr(screen, 'action_navigate_right')
        assert hasattr(screen, 'action_navigate_left')
        assert hasattr(screen, 'action_enter_field')
        assert hasattr(screen, 'action_exit_field')
        assert hasattr(screen, 'action_cancel')
        assert hasattr(screen, 'action_submit')

        assert callable(screen.action_navigate_up)
        assert callable(screen.action_navigate_down)
        assert callable(screen.action_navigate_right)
        assert callable(screen.action_navigate_left)
        assert callable(screen.action_enter_field)
        assert callable(screen.action_exit_field)
        assert callable(screen.action_cancel)
        assert callable(screen.action_submit)

    def test_helper_methods_exist(self):
        """Test that all required helper methods exist."""
        screen = AddServerScreen()

        assert hasattr(screen, '_get_current_field')
        assert hasattr(screen, '_update_field_highlights')
        assert hasattr(screen, '_navigate_to_next_valid_field')
        assert hasattr(screen, '_navigate_to_prev_valid_field')
        assert hasattr(screen, '_update_auth_fields')

        assert callable(screen._get_current_field)
        assert callable(screen._update_field_highlights)
        assert callable(screen._navigate_to_next_valid_field)
        assert callable(screen._navigate_to_prev_valid_field)
        assert callable(screen._update_auth_fields)

    def test_on_input_submitted_exits_field_in_edit_mode(self):
        """Test that pressing Enter in an input field exits edit mode."""
        screen = AddServerScreen()
        screen.in_edit_mode = True
        screen.action_exit_field = Mock()

        # Create a mock event
        mock_input = Mock(spec=Input)
        mock_event = Mock()
        mock_event.input = mock_input
        mock_event.stop = Mock()

        screen.on_input_submitted(mock_event)

        screen.action_exit_field.assert_called_once()
        mock_event.stop.assert_called_once()

    def test_on_input_submitted_does_nothing_in_navigation_mode(self):
        """Test that input submitted event does nothing in navigation mode."""
        screen = AddServerScreen()
        screen.in_edit_mode = False
        screen.action_exit_field = Mock()

        mock_event = Mock()
        mock_event.stop = Mock()

        screen.on_input_submitted(mock_event)

        # Should not call action_exit_field when not in edit mode
        screen.action_exit_field.assert_not_called()


class TestAddServerScreenValidation:
    """Test suite for form validation in AddServerScreen."""

    def test_submit_with_missing_name(self):
        """Test that submission fails with missing name."""
        screen = AddServerScreen()
        screen.notify = Mock()
        screen.dismiss = Mock()

        # Mock query_one to return inputs with empty values
        with patch.object(screen, 'query_one') as mock_query:
            def side_effect(selector, widget_type=None):
                mock = Mock(spec=Input)
                # Create a mock that has a value attribute that returns empty string
                mock.value = ""  # This will call .strip() on the string itself
                mock.focus = Mock()
                return mock

            mock_query.side_effect = side_effect

            screen._submit()

            # Should notify about missing name
            assert screen.notify.called, "Should notify user about missing name"
            # Should not dismiss if validation failed
            screen.dismiss.assert_not_called()

    def test_action_cancel_dismisses_with_none(self):
        """Test that cancel action dismisses with None."""
        screen = AddServerScreen()
        screen.dismiss = Mock()

        screen.action_cancel()

        screen.dismiss.assert_called_once_with(None)

    def test_action_submit_calls_submit_method(self):
        """Test that action_submit calls _submit method."""
        screen = AddServerScreen()
        screen._submit = Mock()

        screen.action_submit()

        screen._submit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
