from unittest.mock import Mock, patch

import pytest
from textual.widgets import Button

from src.ui import AddServerScreen


@pytest.mark.asyncio
async def test_enter_on_cancel_button_action():
    screen = AddServerScreen()
    screen.dismiss = Mock()
    screen._submit = Mock()

    # Setup fields manually since on_mount might not run in this test harness
    screen.fields = [
        {"id": "add-btn", "label_id": None, "type": "button"},
        {"id": "cancel-btn", "label_id": None, "type": "button"},
    ]

    # Navigate to cancel button (index 1)
    screen.current_field_index = 1
    screen.in_edit_mode = False

    # Mock query_one to return a button with proper ID
    with patch.object(screen, "query_one") as mock_query:
        # Create mock button for cancel
        cancel_btn = Mock(spec=Button)
        cancel_btn.id = "cancel-btn"

        # When queried, return this button
        mock_query.return_value = cancel_btn

        # Trigger the action
        screen.action_enter_field()

        # Verify what happened
        # _submit should NOT be called
        # dismiss SHOULD be called

        if screen._submit.called:
            print("FAILURE: _submit() was called!")
        else:
            print("SUCCESS: _submit() was NOT called.")

        if screen.dismiss.called:
            print("SUCCESS: dismiss() was called.")
        else:
            print("FAILURE: dismiss() was NOT called.")

        assert not screen._submit.called
        assert screen.dismiss.called
