"""Type definitions for UI components."""

from typing import NotRequired, TypedDict


class FieldDefinition(TypedDict):
    """Type definition for field definitions in AddServerScreen."""
    id: str
    widget_id: NotRequired[str]  # Widget ID (deprecated, kept for compatibility)
    label_id: NotRequired[str | None]  # Label widget ID, can be None for buttons
    type: NotRequired[str]  # 'input', 'optionlist', or 'button'
    auth_type: NotRequired[str]  # 'key' or 'password', if field is auth-specific
