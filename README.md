# CPU Monitoring TUI Application

A Python-based Terminal User Interface (TUI) for real-time monitoring of CPU core activity across multiple Linux servers via SSH.

## Features

- Real-time CPU and memory monitoring with per-core statistics
- SSH-based remote access with key or password authentication
- **Secure password handling**: Prompted at startup, stored in memory only
- Interactive keyboard navigation with two-level input system
- Collapsible server views with CPU history graphs
- Blue color-coded progress bars for CPU usage visualization
- Dynamic server management (add/delete servers while running)
- Automatic reconnection on network failures
- YAML configuration (passwords never saved to config)
- Async architecture for responsive UI

## Installation

### Prerequisites

- Python 3.9 or higher
- SSH access to target Linux servers
- SSH key files (.pem) for key authentication OR passwords for password authentication

### Setup

```bash
make setup
```

## Configuration

Create/Edit `config.yaml`:

```yaml
servers:
  # SSH Key authentication (recommended)
  - name: "Server 1"
    host: "192.168.1.100"
    username: "ubuntu"
    auth_method: key
    key_path: "~/.ssh/my-key.pem"

  # Password authentication (password prompted at startup)
  - name: "Server 2"
    host: "192.168.1.101"
    username: "ubuntu"
    auth_method: password
    # Note: Password will be prompted securely at startup
    # and stored in memory only (never saved to config file)

monitoring:
  poll_interval: 2.0              # CPU polling interval (seconds)
  ui_refresh_interval: 0.5        # UI refresh rate (seconds)
  connection_timeout: 10          # SSH timeout (seconds)
  max_retries: 3                  # Connection retry attempts
  retry_delay: 5                  # Delay between retries (seconds)

display: {}                       # Reserved for future display options
```

**Authentication Methods:**
- `auth_method: key` - Uses SSH key file (specify `key_path`)
- `auth_method: password` - Password prompted at startup (secure, not saved to config)

## Usage

### Start Application

```bash
make run
```

If you have servers with password authentication, you'll be prompted to enter passwords securely at startup:

```
🔐 Password required for '<name>' (<hostname>)
Enter password for <name>@<hostname>: [hidden input]
```

### Keyboard Controls

**Navigation:**
- `↑/↓` - Navigate between servers
- `←/→` - Collapse/expand server views
- `Enter` - Toggle expand/collapse

**Actions:**
- `R` - Refresh display
- `A` - Add new server (opens dialog)
- `D` - Delete selected server (with confirmation)
- `P` - Open command palette
- `Q` - Quit application

### Display Format

```
Server Name: ✓ 45.2% avg (8 cores)
  Core  0: ████████████░░░░░░░░░░░░░░░░░░  42.3%
  Core  1: ██████████████░░░░░░░░░░░░░░░░  48.7%
```

**Status:**
- ✓ = Connected
- ✗ = Disconnected/error
- → = Selected server
- ▼/▶ = Expanded/collapsed

**Colors:**
- Green: < 30%
- Yellow: 30-70%
- Red: > 70%

## Development

```bash
make test      # Run tests
make format    # Format code
make lint      # Run linters
make check     # Run all checks
make clean     # Remove generated files
```

## Logging

All logs are written to `cpu_monitor.log`. Change log level in `src/main.py`:

```python
logging.basicConfig(level=logging.INFO)  # or logging.DEBUG
```

## Troubleshooting

### SSH Issues

**Key not found** - Verify path in config.yaml

**Connection timeout** - Check network/firewall, increase `connection_timeout`

**Permission denied (key auth)** - Set correct permissions:
```bash
chmod 600 ~/.ssh/your-key.pem
```

**Permission denied (password auth)** - Verify username and password are correct

**Password not prompted** - Ensure `auth_method: password` is set in config.yaml

### Display Issues

**UI not updating** - Check `cpu_monitor.log` for errors

**Incorrect CPU values** - Wait 2-3 poll cycles for accurate measurements

## Technical Details

### Metrics Collection
- **CPU**: Reads `/proc/stat` via SSH, calculates usage from time deltas
- **Memory**: Reads `/proc/meminfo` for real-time memory statistics
- Provides per-core CPU statistics and overall system metrics
- Maintains historical data for graphing

### Architecture
- **SSH**: asyncssh for async I/O
- **Monitoring**: Independent async tasks per server
- **UI**: Textual framework with reactive updates
- **Thread safety**: Async locks for connection management

### Security
- Passwords **never** stored in config files
- Password input via `getpass` (hidden from terminal)
- Passwords kept in memory only during runtime
- Config files safe to commit to version control

## Project Structure

```
src/
├── main.py              # Entry point
├── ssh_client.py        # SSH connection management
├── monitor.py           # CPU monitoring logic
└── ui.py                # TUI components

tests/
├── test_ssh_client.py
├── test_monitor.py
└── test_ui.py

config.yaml              # Configuration
requirements.txt         # Dependencies
Makefile                 # Build commands
```

## Dependencies

**Core:**
- textual - TUI framework
- asyncssh - SSH client
- pyyaml - Configuration

**Development:**
- pytest, pytest-asyncio, pytest-cov, pytest-timeout
- ruff - Fast Python linter and formatter
- pyright - Static type checker

## Development

### Code Quality Tools

This project uses **Ruff** for linting/formatting and **Pyright** for type checking:

```bash
# Run linter
make lint

# Run type checker
make typecheck

# Auto-format code
make format

# Run all checks (lint + typecheck + tests)
make check
```

Configuration is in [pyproject.toml](pyproject.toml).
