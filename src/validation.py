"""Validation utilities for server configuration and user input."""

import ipaddress
import re
from typing import NamedTuple


class ValidationResult(NamedTuple):
    """Result of a validation operation."""

    valid: bool
    error_message: str | None = None


def validate_hostname(hostname: str) -> ValidationResult:
    """Validate a hostname or IP address.

    Args:
        hostname: The hostname or IP address to validate

    Returns:
        ValidationResult indicating if the hostname is valid
    """
    if not hostname or not hostname.strip():
        return ValidationResult(valid=False, error_message="Hostname cannot be empty")

    hostname = hostname.strip()

    # Try to parse as IP address first
    try:
        ipaddress.ip_address(hostname)
        return ValidationResult(valid=True)
    except ValueError:
        pass

    # Validate as hostname (RFC 1123)
    # Hostname rules:
    # - Can contain alphanumeric characters and hyphens
    # - Cannot start or end with hyphen
    # - Each label (part between dots) can be up to 63 characters
    # - Total length up to 253 characters
    # - Must not be just numbers (to avoid confusion with IPs)

    if len(hostname) > 253:
        return ValidationResult(valid=False, error_message="Hostname too long (max 253 characters)")

    # Check if hostname is all digits (would be confused with IP)
    if hostname.replace(".", "").isdigit():
        return ValidationResult(valid=False, error_message="Invalid IP address format")

    # Hostname pattern: alphanumeric and hyphens, with dots separating labels
    hostname_pattern = re.compile(
        r"^(?!-)"  # Cannot start with hyphen
        r"(?:[a-zA-Z0-9-]{1,63}\.)*"  # Labels separated by dots
        r"[a-zA-Z0-9-]{1,63}"  # Final label
        r"(?<!-)$"  # Cannot end with hyphen
    )

    if not hostname_pattern.match(hostname):
        return ValidationResult(
            valid=False,
            error_message="Invalid hostname format (use alphanumeric, hyphens, and dots)"
        )

    # Check each label doesn't start/end with hyphen
    labels = hostname.split(".")
    for label in labels:
        if label.startswith("-") or label.endswith("-"):
            return ValidationResult(
                valid=False,
                error_message=f"Hostname label '{label}' cannot start or end with hyphen"
            )

    return ValidationResult(valid=True)


def validate_username(username: str) -> ValidationResult:
    """Validate a username for SSH.

    Args:
        username: The username to validate

    Returns:
        ValidationResult indicating if the username is valid
    """
    if not username or not username.strip():
        return ValidationResult(valid=False, error_message="Username cannot be empty")

    username = username.strip()

    # Username validation rules (POSIX.1-2017):
    # - Can contain lowercase letters, digits, underscore, and hyphen
    # - Should start with a letter or underscore
    # - Typically limited to 32 characters (though can be longer on some systems)
    # - We'll be more permissive and allow uppercase as well

    if len(username) > 32:
        return ValidationResult(
            valid=False,
            error_message="Username too long (max 32 characters recommended)"
        )

    # Allow alphanumeric, underscore, hyphen, and dot (common in practice)
    username_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9._-]*$")

    if not username_pattern.match(username):
        return ValidationResult(
            valid=False,
            error_message="Invalid username format (must start with letter/underscore, "
                         "contain only alphanumeric, underscore, hyphen, or dot)"
        )

    return ValidationResult(valid=True)


def validate_server_name(name: str) -> ValidationResult:
    """Validate a server display name.

    Args:
        name: The server name to validate

    Returns:
        ValidationResult indicating if the name is valid
    """
    if not name or not name.strip():
        return ValidationResult(valid=False, error_message="Server name cannot be empty")

    name = name.strip()

    if len(name) > 64:
        return ValidationResult(valid=False, error_message="Server name too long (max 64 characters)")

    # Allow most characters but avoid control characters
    if any(ord(c) < 32 for c in name):
        return ValidationResult(
            valid=False,
            error_message="Server name contains invalid control characters"
        )

    return ValidationResult(valid=True)


def validate_port(port: str | int) -> ValidationResult:
    """Validate a port number.

    Args:
        port: The port number to validate (as string or int)

    Returns:
        ValidationResult indicating if the port is valid
    """
    try:
        port_num = int(port)
    except (ValueError, TypeError):
        return ValidationResult(valid=False, error_message="Port must be a number")

    if port_num < 1 or port_num > 65535:
        return ValidationResult(
            valid=False,
            error_message="Port must be between 1 and 65535"
        )

    return ValidationResult(valid=True)
