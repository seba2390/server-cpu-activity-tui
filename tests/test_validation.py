"""Tests for validation utilities."""


from src.validation import (
    validate_hostname,
    validate_port,
    validate_server_name,
    validate_username,
)


class TestValidateHostname:
    """Tests for hostname validation."""

    def test_valid_ipv4(self):
        """Test valid IPv4 addresses."""
        assert validate_hostname("192.168.1.1").valid
        assert validate_hostname("10.0.0.1").valid
        assert validate_hostname("172.16.0.1").valid
        assert validate_hostname("8.8.8.8").valid

    def test_valid_ipv6(self):
        """Test valid IPv6 addresses."""
        assert validate_hostname("::1").valid
        assert validate_hostname("2001:db8::1").valid
        assert validate_hostname("fe80::1").valid

    def test_valid_hostname(self):
        """Test valid hostnames."""
        assert validate_hostname("example.com").valid
        assert validate_hostname("sub.example.com").valid
        assert validate_hostname("my-server").valid
        assert validate_hostname("server1").valid
        assert validate_hostname("my-server.local").valid

    def test_invalid_empty(self):
        """Test empty hostname."""
        result = validate_hostname("")
        assert not result.valid
        assert "empty" in result.error_message.lower()

    def test_invalid_too_long(self):
        """Test hostname that's too long."""
        long_hostname = "a" * 254
        result = validate_hostname(long_hostname)
        assert not result.valid
        assert "too long" in result.error_message.lower()

    def test_invalid_starts_with_hyphen(self):
        """Test hostname starting with hyphen."""
        result = validate_hostname("-invalid.com")
        assert not result.valid

    def test_invalid_ends_with_hyphen(self):
        """Test hostname ending with hyphen."""
        result = validate_hostname("invalid-.com")
        assert not result.valid

    def test_invalid_special_characters(self):
        """Test hostname with invalid characters."""
        result = validate_hostname("invalid_host.com")
        assert not result.valid

    def test_invalid_ip_format(self):
        """Test invalid IP address."""
        result = validate_hostname("999.999.999.999")
        assert not result.valid


class TestValidateUsername:
    """Tests for username validation."""

    def test_valid_username(self):
        """Test valid usernames."""
        assert validate_username("user").valid
        assert validate_username("john.doe").valid
        assert validate_username("user123").valid
        assert validate_username("_user").valid
        assert validate_username("user-name").valid

    def test_invalid_empty(self):
        """Test empty username."""
        result = validate_username("")
        assert not result.valid
        assert "empty" in result.error_message.lower()

    def test_invalid_starts_with_number(self):
        """Test username starting with number."""
        result = validate_username("123user")
        assert not result.valid

    def test_invalid_special_characters(self):
        """Test username with invalid characters."""
        result = validate_username("user@host")
        assert not result.valid
        result = validate_username("user space")
        assert not result.valid

    def test_invalid_too_long(self):
        """Test username that's too long."""
        long_username = "a" * 33
        result = validate_username(long_username)
        assert not result.valid
        assert "too long" in result.error_message.lower()

    def test_valid_edge_cases(self):
        """Test edge cases that should be valid."""
        assert validate_username("_").valid
        assert validate_username("a").valid
        assert validate_username("a" * 32).valid


class TestValidateServerName:
    """Tests for server name validation."""

    def test_valid_server_name(self):
        """Test valid server names."""
        assert validate_server_name("Production Server").valid
        assert validate_server_name("server-1").valid
        assert validate_server_name("My Server (Dev)").valid
        assert validate_server_name("🚀 Server").valid

    def test_invalid_empty(self):
        """Test empty server name."""
        result = validate_server_name("")
        assert not result.valid
        assert "empty" in result.error_message.lower()

    def test_invalid_too_long(self):
        """Test server name that's too long."""
        long_name = "a" * 65
        result = validate_server_name(long_name)
        assert not result.valid
        assert "too long" in result.error_message.lower()

    def test_invalid_control_characters(self):
        """Test server name with control characters."""
        result = validate_server_name("server\x00name")
        assert not result.valid
        assert "control" in result.error_message.lower()

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        result = validate_server_name("   server   ")
        assert result.valid


class TestValidatePort:
    """Tests for port validation."""

    def test_valid_port_number(self):
        """Test valid port numbers."""
        assert validate_port(22).valid
        assert validate_port(80).valid
        assert validate_port(443).valid
        assert validate_port(8080).valid
        assert validate_port(65535).valid
        assert validate_port(1).valid

    def test_valid_port_string(self):
        """Test valid port numbers as strings."""
        assert validate_port("22").valid
        assert validate_port("8080").valid

    def test_invalid_port_too_low(self):
        """Test port number too low."""
        result = validate_port(0)
        assert not result.valid
        result = validate_port(-1)
        assert not result.valid

    def test_invalid_port_too_high(self):
        """Test port number too high."""
        result = validate_port(65536)
        assert not result.valid
        result = validate_port(99999)
        assert not result.valid

    def test_invalid_port_not_a_number(self):
        """Test non-numeric port."""
        result = validate_port("abc")
        assert not result.valid
        assert "number" in result.error_message.lower()
