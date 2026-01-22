# CPU Monitoring TUI Application

A Python-based Terminal User Interface (TUI) for real-time monitoring of CPU core activity across multiple Linux servers via SSH.

## Features

- Real-time CPU monitoring with per-core statistics
- SSH-based remote access using key authentication
- Interactive keyboard navigation
- Collapsible server views
- Color-coded usage levels (green/yellow/red)
- Automatic reconnection on network failures
- YAML configuration
- Async architecture for responsive UI

## Installation

### Prerequisites

- Python 3.9 or higher
- SSH access to target Linux servers
- SSH key files (.pem) for authentication

### Setup

```bash
make setup
```

## Configuration

Create/Edit `config.yaml`:

```yaml
servers:
  - name: "Server 1"
    host: "192.168.1.100"
    username: "ubuntu"
    key_path: "~/.ssh/my-key.pem"

monitoring:
  poll_interval: 2.0              # CPU polling interval (seconds)
  ui_refresh_interval: 0.5        # UI refresh rate (seconds)
  connection_timeout: 10          # SSH timeout (seconds)
  max_retries: 3                  # Connection retry attempts
  retry_delay: 5                  # Delay between retries (seconds)

display:
  low_threshold: 30               # Green threshold (%)
  medium_threshold: 70            # Yellow threshold (%)
  start_collapsed: false          # Initial state
```

## Usage

### Start Application

```bash
make run
```

### Keyboard Controls

- `↑/↓` - Navigate between servers
- `←/→` - Collapse/expand server views
- `Enter` - Toggle expand/collapse
- `R` - Refresh display
- `Q` - Quit

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

**Permission denied** - Set correct permissions:
```bash
chmod 600 ~/.ssh/your-key.pem
```

### Display Issues

**UI not updating** - Check `cpu_monitor.log` for errors

**Incorrect CPU values** - Wait 2-3 poll cycles for accurate measurements

## Technical Details

### CPU Metrics
- Reads `/proc/stat` via SSH
- Calculates usage from time deltas
- Provides per-core and overall statistics

### Architecture
- **SSH**: asyncssh for async I/O
- **Monitoring**: Independent async tasks per server
- **UI**: Textual framework with reactive updates
- **Thread safety**: Async locks

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
- pytest, pytest-asyncio, pytest-cov
- black, mypy, flake8
