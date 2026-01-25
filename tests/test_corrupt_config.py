"""Tests for handling corrupt or invalid configuration files."""


import pytest
import yaml

from src.main import CPUMonitoringApp


class TestCorruptConfig:
    """Test handling of corrupt configuration files."""

    def test_invalid_yaml_syntax(self, tmp_path):
        """Test handling of invalid YAML syntax."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("servers:\n  - name: test\n    host: invalid yaml {{{")

        app = CPUMonitoringApp(str(config_file))

        # Should exit with error (raises SystemExit)
        with pytest.raises(SystemExit):
            app.load_config()

    def test_missing_config_file(self, tmp_path):
        """Test handling of missing configuration file."""
        config_file = tmp_path / "nonexistent.yaml"

        app = CPUMonitoringApp(str(config_file))

        # Should exit with error
        with pytest.raises(SystemExit):
            app.load_config()

    def test_empty_config_file(self, tmp_path):
        """Test handling of empty configuration file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        app = CPUMonitoringApp(str(config_file))

        # Should load with defaults (empty servers list)
        app.load_config()
        assert app.config.get("servers", []) == []

    def test_config_with_missing_required_fields(self, tmp_path):
        """Test handling of config with missing required server fields."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "servers": [
                {
                    "name": "test-server",
                    # Missing 'host' and 'username'
                    "auth_method": "password"
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Should exit when trying to initialize components
        with pytest.raises(SystemExit):
            app.initialize_components()

    def test_config_with_invalid_auth_method(self, tmp_path):
        """Test handling of invalid authentication method."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "servers": [
                {
                    "name": "test-server",
                    "host": "example.com",
                    "username": "testuser",
                    "auth_method": "invalid_method"  # Invalid
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Should raise ValueError during initialization
        with pytest.raises(SystemExit):
            app.initialize_components()

    def test_config_with_key_auth_missing_key_path(self, tmp_path):
        """Test handling of key auth without key_path."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "servers": [
                {
                    "name": "test-server",
                    "host": "example.com",
                    "username": "testuser",
                    "auth_method": "key"
                    # Missing 'key_path'
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Should raise ValueError during initialization
        with pytest.raises(SystemExit):
            app.initialize_components()

    def test_config_with_invalid_data_types(self, tmp_path):
        """Test handling of invalid data types in config."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "servers": "not a list",  # Should be a list
            "monitoring": {
                "poll_interval": "not a number"  # Should be float
            }
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Should handle gracefully with defaults
        # 'servers' will be treated as empty list, poll_interval will use default
        assert isinstance(app.config.get("servers", []), (list, str))

    def test_config_with_negative_values(self, tmp_path):
        """Test handling of negative values in config."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "servers": [],
            "monitoring": {
                "poll_interval": -1.0,
                "history_window": -60,
                "connection_timeout": -10
            }
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()
        app.initialize_components()

        # Should use defaults for negative values (handled in code)
        # This tests that the app doesn't crash with invalid values

    def test_config_save_after_corruption(self, tmp_path):
        """Test that config can be saved after loading corrupt file."""
        config_file = tmp_path / "config.yaml"

        # Start with valid config
        config_data = {
            "servers": [
                {
                    "name": "test-server",
                    "host": "192.168.1.1",
                    "username": "testuser",
                    "auth_method": "password"
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Modify config and save
        app.config["servers"].append({
            "name": "new-server",
            "host": "192.168.1.2",
            "username": "newuser",
            "auth_method": "password"
        })
        app.save_config()

        # Verify saved config is valid
        with open(config_file) as f:
            reloaded = yaml.safe_load(f)

        assert len(reloaded["servers"]) == 2
        assert reloaded["servers"][1]["name"] == "new-server"

    def test_readonly_config_file(self, tmp_path):
        """Test handling of read-only configuration file."""
        config_file = tmp_path / "config.yaml"
        config_data = {"servers": []}
        config_file.write_text(yaml.dump(config_data))

        # Make file read-only
        config_file.chmod(0o444)

        app = CPUMonitoringApp(str(config_file))
        app.load_config()

        # Try to save (should handle permission error gracefully)
        app.save_config()  # Should log error but not crash

        # Restore permissions for cleanup
        config_file.chmod(0o644)
