# osx-cpu-monitor

**Interactive command-line system monitor application for macOS.**

## Features

- **Real-time CPU monitoring** with detailed or simplified views
- **Real-time network throughput** monitoring
- **Threshold alerts** to notify of high CPU or network usage
- **Flexible display modes**: CPU-only, Network-only, or Combined dashboard
- Configurable update interval

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/osx-cpu-monitor.git
   cd osx-cpu-monitor
   ```
2. (Optional) Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main dashboard entry point:

```bash
./dashboard.py [OPTIONS]
```

### Common Options

| Flag                   | Description                                           | Default  |
|------------------------|-------------------------------------------------------|----------|
| `-i`, `--interval`     | Update interval in seconds                            | `1.0`    |
| `-s`, `--simple`       | Use simplified view (less detail)                     | off      |
| `-n`, `--no-alerts`    | Disable threshold alerts                              | off      |
| `--cpu-only`           | Show only CPU metrics                                 | on       |
| `--network-only`       | Show only network metrics                             | off      |
| `--all`                | Show both CPU and network metrics                     | off      |

## Examples

- **CPU-only monitor** (default):
  ```bash
  ./dashboard.py
  ```
- **Combined dashboard with 2-second updates**:
  ```bash
  ./dashboard.py --all -i 2.0
  ```
- **Network-only simplified view, no alerts**:
  ```bash
  ./dashboard.py --network-only --simple --no-alerts
  ```


## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

