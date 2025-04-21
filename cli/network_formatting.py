"""
Terminal formatting utilities for displaying network metrics.
"""
import os
import math
from typing import Dict, List, Any, Optional, Tuple, Union

from cli.formatting import (
    Colors, create_progress_bar, get_terminal_size
)


def format_bandwidth(
    rx_bytes_per_sec: float,
    tx_bytes_per_sec: float,
    width: int = 25,
) -> str:
    """
    Format bandwidth usage with a dual progress bar for received and sent data.
    
    Args:
        rx_bytes_per_sec: Bytes received per second
        tx_bytes_per_sec: Bytes transmitted per second
        width: Width of the progress bars
        
    Returns:
        Formatted string with bandwidth information and bars
    """
    # Convert bytes to more readable units
    def format_bytes_per_sec(bytes_per_sec: float) -> str:
        if bytes_per_sec >= 1_000_000:  # MB/s
            return f"{bytes_per_sec/1_000_000:.2f} MB/s"
        elif bytes_per_sec >= 1_000:  # KB/s
            return f"{bytes_per_sec/1_000:.2f} KB/s"
        else:  # B/s
            return f"{bytes_per_sec:.0f} B/s"
    
    rx_str = format_bytes_per_sec(rx_bytes_per_sec)
    tx_str = format_bytes_per_sec(tx_bytes_per_sec)
    
    # Determine a reasonable max value for progress bars
    # Start small and adjust up based on actual values
    max_val = 100_000  # Default to 100 KB/s
    
    # Adjust based on actual traffic
    max_bytes = max(rx_bytes_per_sec, tx_bytes_per_sec)
    if max_bytes > max_val:
        # Scale up to next reasonable threshold
        if max_bytes >= 10_000_000:  # 10 MB/s
            max_val = 100_000_000  # 100 MB/s
        elif max_bytes >= 1_000_000:  # 1 MB/s
            max_val = 10_000_000  # 10 MB/s
        elif max_bytes >= 100_000:  # 100 KB/s
            max_val = 1_000_000  # 1 MB/s
        else:
            max_val = 1_000_000  # 1 MB/s
    
    # Create the progress bars
    rx_bar = create_progress_bar(rx_bytes_per_sec, max_val, width, color_gradient=True)
    tx_bar = create_progress_bar(tx_bytes_per_sec, max_val, width, color_gradient=True)
    
    # Format the output
    download_label = f"{Colors.BOLD}↓ Received{Colors.RESET}:"
    upload_label = f"{Colors.BOLD}↑ Sent{Colors.RESET}:    "
    
    download_line = f"{download_label} {rx_bar} {rx_str}"
    upload_line = f"{upload_label} {tx_bar} {tx_str}"
    
    return f"{download_line}\n{upload_line}"


def format_data_transferred(
    rx_bytes: int,
    tx_bytes: int,
) -> str:
    """
    Format total data transferred.
    
    Args:
        rx_bytes: Total bytes received
        tx_bytes: Total bytes transmitted
        
    Returns:
        Formatted string with data transferred information
    """
    # Convert bytes to more readable units
    def format_bytes(bytes_val: int) -> str:
        if bytes_val >= 1_000_000_000:  # GB
            return f"{bytes_val/1_000_000_000:.2f} GB"
        elif bytes_val >= 1_000_000:  # MB
            return f"{bytes_val/1_000_000:.2f} MB"
        elif bytes_val >= 1_000:  # KB
            return f"{bytes_val/1_000:.2f} KB"
        else:  # B
            return f"{bytes_val} B"
    
    rx_str = format_bytes(rx_bytes)
    tx_str = format_bytes(tx_bytes)
    total_str = format_bytes(rx_bytes + tx_bytes)
    
    label = f"{Colors.BOLD}Data Transferred{Colors.RESET}:"
    
    return f"{label} {Colors.FG_CYAN}↓ {rx_str}{Colors.RESET} | {Colors.FG_MAGENTA}↑ {tx_str}{Colors.RESET} | Total: {total_str}"


def format_interface_status(
    name: str,
    status: str,
    ipv4: List[str],
    rx_bytes: int,
    tx_bytes: int,
    is_wifi: bool = False,
    wifi_signal: Optional[int] = None,
    max_name_length: int = 8,
) -> str:
    """
    Format network interface status.
    
    Args:
        name: Interface name
        status: Interface status
        ipv4: List of IPv4 addresses
        rx_bytes: Bytes received
        tx_bytes: Bytes transmitted
        is_wifi: Whether this is a WiFi interface
        wifi_signal: WiFi signal strength (RSSI) if available
        max_name_length: Maximum length for interface name
        
    Returns:
        Formatted string with interface information
    """
    # Truncate name if needed
    if len(name) > max_name_length:
        display_name = name[:max_name_length-1] + "…"
    else:
        display_name = name.ljust(max_name_length)
    
    # Format status with color
    if status.lower() == "active":
        status_color = Colors.FG_GREEN
    else:
        status_color = Colors.FG_RED
    status_str = f"{status_color}{status}{Colors.RESET}"
    
    # Format IP addresses
    ip_str = ", ".join(ipv4) if ipv4 else "No IP"
    
    # Format traffic
    def format_bytes(bytes_val: int) -> str:
        if bytes_val >= 1_000_000_000:  # GB
            return f"{bytes_val/1_000_000_000:.2f} GB"
        elif bytes_val >= 1_000_000:  # MB
            return f"{bytes_val/1_000_000:.2f} MB"
        else:  # KB
            return f"{bytes_val/1_000:.1f} KB"
    
    rx_str = format_bytes(rx_bytes)
    tx_str = format_bytes(tx_bytes)
    
    # WiFi signal if available
    wifi_icon = "📶 " if is_wifi else ""
    signal_str = ""
    
    if is_wifi and wifi_signal is not None:
        # RSSI is typically -30 (excellent) to -90 (poor)
        if wifi_signal > -50:
            signal_color = Colors.FG_GREEN
        elif wifi_signal > -70:
            signal_color = Colors.FG_YELLOW
        else:
            signal_color = Colors.FG_RED
            
        signal_str = f" {wifi_icon}{signal_color}{wifi_signal} dBm{Colors.RESET}"
    
    return f"{Colors.BOLD}{display_name}{Colors.RESET} [{status_str}] {ip_str}{signal_str} (↓ {rx_str}, ↑ {tx_str})"


def format_network_process(
    name: str,
    rx_bytes: int,
    tx_bytes: int,
    bandwidth: float,
    max_name_length: int = 25,
    width: int = 15,
) -> str:
    """
    Format network process usage for display.
    
    Args:
        name: Process name
        rx_bytes: Bytes received
        tx_bytes: Bytes transmitted
        bandwidth: Current bandwidth usage in bytes/sec
        max_name_length: Maximum length for process name truncation
        width: Width of the progress bar
        
    Returns:
        Formatted string with process network usage information
    """
    # Truncate name if needed
    if len(name) > max_name_length:
        name = name[:max_name_length - 3] + "..."
    else:
        name = name.ljust(max_name_length)
    
    # Format bandwidth with appropriate units
    def format_bandwidth(bytes_per_sec: float) -> str:
        if bytes_per_sec >= 1_000_000:  # MB/s
            return f"{bytes_per_sec/1_000_000:.2f} MB/s"
        elif bytes_per_sec >= 1_000:  # KB/s
            return f"{bytes_per_sec/1_000:.2f} KB/s"
        else:  # B/s
            return f"{bytes_per_sec:.0f} B/s"
    
    bandwidth_str = format_bandwidth(bandwidth)
    
    # Format total data transferred
    def format_bytes(bytes_val: int) -> str:
        if bytes_val >= 1_000_000_000:  # GB
            return f"{bytes_val/1_000_000_000:.2f} GB"
        elif bytes_val >= 1_000_000:  # MB
            return f"{bytes_val/1_000_000:.2f} MB"
        else:  # KB or B
            return f"{bytes_val/1_000:.1f} KB"
    
    rx_str = format_bytes(rx_bytes)
    tx_str = format_bytes(tx_bytes)
    
    # Determine a reasonable max value for the progress bar
    # This would depend on typical network usage
    max_val = 1_000_000  # 1 MB/s
    if bandwidth > max_val:
        # Scale up to a reasonable threshold based on actual usage
        max_val = max(bandwidth, max_val) * 1.2
    
    # Create progress bar
    bar = create_progress_bar(bandwidth, max_val, width)
    
    return f"{name} {bar} {bandwidth_str} (↓ {rx_str}, ↑ {tx_str})"


def create_interfaces_table(
    interfaces: List[Dict[str, Any]],
    max_width: int = 80,
    include_inactive: bool = False,
) -> str:
    """
    Create a formatted table of network interface information.
    
    Args:
        interfaces: List of interface data dictionaries
        max_width: Maximum width of the output
        include_inactive: Whether to include inactive interfaces
        
    Returns:
        Formatted table as a string
    """
    # Determine available width
    term_width, _ = get_terminal_size()
    width = min(term_width, max_width)
    
    # Create header
    header = f"{Colors.BOLD}{'Interface':10s} {'Status':8s} {'IP Address':15s} {'Data Received':15s} {'Data Sent':15s}{Colors.RESET}"
    
    # Create rows
    rows = []
    for interface in interfaces:
        # Skip inactive interfaces if requested
        if not include_inactive and interface.get('status', '').lower() != 'active':
            continue
            
        name = interface.get('name', 'unknown')
        status = interface.get('status', 'unknown')
        ipv4 = interface.get('ipv4_addresses', [])
        
        rx_bytes = interface.get('rx_bytes', 0)
        tx_bytes = interface.get('tx_bytes', 0)
        
        is_wifi = False
        wifi_signal = None
        
        # Check if this is a WiFi interface
        if name.startswith('en') and interface.get('status', '').lower() == 'active':
            is_wifi = True
            wifi_signal = interface.get('wifi_signal_strength')
        
        row = format_interface_status(
            name=name,
            status=status,
            ipv4=ipv4,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
            is_wifi=is_wifi,
            wifi_signal=wifi_signal,
            max_name_length=10
        )
        rows.append(row)
    
    # Combine header and rows
    divider = "─" * width
    return f"{header}\n{Colors.FG_BRIGHT_BLACK}{divider}{Colors.RESET}\n" + "\n".join(rows)


def create_network_processes_table(
    processes: List[Dict[str, Any]],
    max_width: int = 80,
    max_processes: int = 5,
) -> str:
    """
    Create a formatted table of top network-consuming processes.
    
    Args:
        processes: List of process data dictionaries
        max_width: Maximum width of the output
        max_processes: Maximum number of processes to show
        
    Returns:
        Formatted table as a string
    """
    # Determine available width
    term_width, _ = get_terminal_size()
    width = min(term_width, max_width)
    
    # Calculate column widths
    name_width = width - 55
    name_width = max(15, name_width)  # Ensure minimum width
    
    bar_width = 15
    
    # Create header
    header = f"{Colors.BOLD}{'Process':{name_width}s} {'Bandwidth':{bar_width+10}s} {'Data Received':15s} {'Data Sent':15s}{Colors.RESET}"
    
    # Create rows
    rows = []
    for i, proc in enumerate(processes):
        if i >= max_processes:
            break
            
        name = proc.get('name', 'unknown')
        rx_bytes = proc.get('rx_bytes', 0)
        tx_bytes = proc.get('tx_bytes', 0)
        bandwidth = proc.get('bandwidth', 0.0)
        
        row = format_network_process(
            name=name,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
            bandwidth=bandwidth,
            max_name_length=name_width,
            width=bar_width
        )
        rows.append(row)
    
    # Combine header and rows
    divider = "─" * width
    return f"{header}\n{Colors.FG_BRIGHT_BLACK}{divider}{Colors.RESET}\n" + "\n".join(rows)


def create_connections_summary(
    connections: Dict[str, int],
    width: int = 60,
) -> str:
    """
    Create a string summarizing network connections.
    
    Args:
        connections: Dictionary with connection counts
        width: Width for formatting
        
    Returns:
        Formatted connection summary
    """
    tcp = connections.get('tcp', 0)
    udp = connections.get('udp', 0)
    total = connections.get('total', 0)
    established = connections.get('established', 0)
    listening = connections.get('listening', 0)
    
    # Format with colors
    total_str = f"{Colors.BOLD}{total}{Colors.RESET}"
    tcp_str = f"{Colors.FG_CYAN}{tcp}{Colors.RESET}"
    udp_str = f"{Colors.FG_MAGENTA}{udp}{Colors.RESET}"
    established_str = f"{Colors.FG_GREEN}{established}{Colors.RESET}"
    listening_str = f"{Colors.FG_YELLOW}{listening}{Colors.RESET}"
    
    return f"Connections: {total_str} total ({tcp_str} TCP, {udp_str} UDP, {established_str} established, {listening_str} listening)"


def create_wifi_summary(
    wifi_info: Dict[str,Any],
    width: int = 60,
) -> Optional[str]:
    """
    Create a string summarizing WiFi information.
    
    Args:
        wifi_info: Dictionary with WiFi information
        width: Width for formatting
        
    Returns:
        Formatted WiFi summary or None if WiFi is not connected
    """
    if not wifi_info.get('connected', False):
        return None
    
    ssid = wifi_info.get('ssid', 'Unknown')
    signal = wifi_info.get('signal_strength', 0)
    noise = wifi_info.get('noise', 0)
    snr = wifi_info.get('signal_to_noise', 0)
    channel = wifi_info.get('channel', 'Unknown')
    tx_rate = wifi_info.get('tx_rate', 0)
    security = wifi_info.get('security', 'Unknown')
    
    # Format signal strength with color
    if signal > -50:
        signal_color = Colors.FG_GREEN
    elif signal > -70:
        signal_color = Colors.FG_YELLOW
    else:
        signal_color = Colors.FG_RED
        
    signal_str = f"{signal_color}{signal} dBm{Colors.RESET}"
    
    # Format SNR with color
    if snr > 30:
        snr_color = Colors.FG_GREEN
    elif snr > 20:
        snr_color = Colors.FG_YELLOW
    else:
        snr_color = Colors.FG_RED
        
    snr_str = f"{snr_color}{snr} dB{Colors.RESET}"
    
    # Combine information
    wifi_icon = "📶"
    ssid_str = f"{Colors.BOLD}{ssid}{Colors.RESET}"
    channel_str = f"{Colors.FG_CYAN}{channel}{Colors.RESET}"
    rate_str = f"{Colors.FG_MAGENTA}{tx_rate} Mbps{Colors.RESET}"
    
    return f"{wifi_icon} {ssid_str} | Signal: {signal_str} | SNR: {snr_str} | Channel: {channel_str} | Rate: {rate_str} | Security: {security}"




def create_bandwidth_history_graph(
    rx_history: List[float],
    tx_history: List[float],
    width: int = 50,
    height: int = 5,
) -> str:
    """
    Create a graph showing bandwidth usage history over time.
    
    Args:
        rx_history: List of receive bandwidth values
        tx_history: List of transmit bandwidth values
        width: Width of the graph in characters
        height: Height of the graph in characters (1-8)
        
    Returns:
        ASCII graph of bandwidth history
    """
    # Ensure height is in valid range for block characters
    height = min(max(1, height), 8)
    
    # If histories are empty, return an empty graph
    if not rx_history and not tx_history:
        return "No bandwidth history available yet."
    
    # Determine the graph width based on available data and requested width
    data_points = min(width, max(len(rx_history), len(tx_history)))
    if data_points == 0:
        return "No bandwidth history available yet."
    
    # Block characters for different heights (1/8 to 8/8)
    blocks = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    
    # Sample or pad the history data to fit the width
    if len(rx_history) > data_points:
        # Sample evenly from the history
        step = len(rx_history) / data_points
        rx_data = [rx_history[min(len(rx_history) - 1, int(i * step))] for i in range(data_points)]
    else:
        # Pad with zeros if we don't have enough data
        rx_data = [0] * (data_points - len(rx_history)) + rx_history[-data_points:]
    
    if len(tx_history) > data_points:
        # Sample evenly from the history
        step = len(tx_history) / data_points
        tx_data = [tx_history[min(len(tx_history) - 1, int(i * step))] for i in range(data_points)]
    else:
        # Pad with zeros if we don't have enough data
        tx_data = [0] * (data_points - len(tx_history)) + tx_history[-data_points:]
    
    # Find the maximum value for scaling
    max_value = max(max(rx_data, default=0), max(tx_data, default=0))
    if max_value == 0:
        max_value = 1  # Avoid division by zero
    
    # Units formatting
    if max_value >= 1_000_000:  # MB/s range
        unit = "MB/s"
        scale_factor = 1_000_000
    elif max_value >= 1_000:  # KB/s range
        unit = "KB/s"
        scale_factor = 1_000
    else:  # B/s range
        unit = "B/s"
        scale_factor = 1
    
    # Create a visually appealing y-axis scale
    max_scale = (max_value / scale_factor) * 1.1  # Add 10% headroom
    
    # Scale the data to the graph height (0-8 scale for the block characters)
    rx_scaled = [min(8, int((val / max_value) * 8)) for val in rx_data]
    tx_scaled = [min(8, int((val / max_value) * 8)) for val in tx_data]
    
    # Create the graph
    rx_line = ''.join(blocks[h] for h in rx_scaled)
    tx_line = ''.join(blocks[h] for h in tx_scaled)
    
    # Build the output with color
    result = []
    result.append(f"Bandwidth History (max: {max_scale:.2f} {unit})")
    result.append(f"{Colors.FG_CYAN}↓ Received:{Colors.RESET} {rx_line}")
    result.append(f"{Colors.FG_MAGENTA}↑ Sent:    {Colors.RESET} {tx_line}")
    
    return '\n'.join(result)


def format_live_bandwidth(
    rx_bytes_per_sec: float,
    tx_bytes_per_sec: float,
    width: int = 25,
    show_numeric: bool = True, 
    show_units: bool = True,
) -> str:
    """
    Format bandwidth usage with more dynamic visual indicators.
    
    Args:
        rx_bytes_per_sec: Bytes received per second
        tx_bytes_per_sec: Bytes transmitted per second
        width: Width of the progress bars
        show_numeric: Whether to show numeric values
        show_units: Whether to show units (KB/s, MB/s)
        
    Returns:
        Formatted string with dynamic bandwidth visualization
    """
    # Convert bytes to more readable units
    def format_bytes_per_sec(bytes_per_sec: float) -> str:
        if bytes_per_sec >= 1_000_000:  # MB/s
            return f"{bytes_per_sec/1_000_000:.2f} MB/s"
        elif bytes_per_sec >= 1_000:  # KB/s
            return f"{bytes_per_sec/1_000:.2f} KB/s"
        else:  # B/s
            return f"{bytes_per_sec:.0f} B/s"
    
    rx_str = format_bytes_per_sec(rx_bytes_per_sec)
    tx_str = format_bytes_per_sec(tx_bytes_per_sec)
    
    # Determine a reasonable max value based on actual traffic
    max_bytes = max(rx_bytes_per_sec, tx_bytes_per_sec, 1000)  # Minimum 1KB/s for scale
    
    # Scale up to reasonable max
    if max_bytes >= 10_000_000:  # > 10MB/s
        max_val = 100_000_000  # 100MB/s
    elif max_bytes >= 1_000_000:  # > 1MB/s
        max_val = 10_000_000  # 10MB/s
    elif max_bytes >= 100_000:  # > 100KB/s
        max_val = 1_000_000  # 1MB/s
    elif max_bytes >= 10_000:  # > 10KB/s
        max_val = 100_000  # 100KB/s
    else:
        max_val = 10_000  # 10KB/s
    
    # Create dynamic progress bars
    rx_bar_width = int((rx_bytes_per_sec / max_val) * width)
    tx_bar_width = int((tx_bytes_per_sec / max_val) * width)
    
    # Ensure at least one character if there's any traffic
    rx_bar_width = max(1, rx_bar_width) if rx_bytes_per_sec > 0 else 0
    tx_bar_width = max(1, tx_bar_width) if tx_bytes_per_sec > 0 else 0
    
    # Create bars with animation effect based on activity level
    def create_animated_bar(bytes_per_sec: float, bar_width: int, color: str) -> str:
        if bar_width == 0:
            return color + " " * width + Colors.RESET
            
        # Create an animated effect based on activity level
        if bytes_per_sec > 1_000_000:  # > 1MB/s
            chars = "■□■□■□■□"  # High activity pattern
        elif bytes_per_sec > 100_000:  # > 100KB/s
            chars = "■■□□"  # Medium activity pattern
        else:
            chars = "■□"  # Low activity pattern
            
        # Create pattern based on current timestamp for animation
        t = int(time.time() * 2) % len(chars)
        pattern = chars[t:] + chars[:t]
        repeats = (bar_width // len(pattern)) + 1
        bar_content = (pattern * repeats)[:bar_width]
        
        # Fill the rest with empty space
        return color + bar_content + " " * (width - bar_width) + Colors.RESET
    
    # Create the animated bars
    rx_bar = create_animated_bar(rx_bytes_per_sec, rx_bar_width, Colors.FG_CYAN)
    tx_bar = create_animated_bar(tx_bytes_per_sec, tx_bar_width, Colors.FG_MAGENTA)
    
    # Format the output
    download_label = f"{Colors.BOLD}↓ Received{Colors.RESET}:"
    upload_label = f"{Colors.BOLD}↑ Sent{Colors.RESET}:    "
    
    if show_numeric:
        download_line = f"{download_label} {rx_bar} {rx_str}"
        upload_line = f"{upload_label} {tx_bar} {tx_str}"
    else:
        download_line = f"{download_label} {rx_bar}"
        upload_line = f"{upload_label} {tx_bar}"
    
    return f"{download_line}\n{upload_line}"


def format_active_connection_indicator(connection_count: int, max_connections: int = 1000) -> str:
    """
    Create a visual indicator of active network connections.
    
    Args:
        connection_count: Number of active connections
        max_connections: Maximum connection count for scaling
        
    Returns:
        Animated/dynamic connection indicator
    """
    # Normalize connection count to a scale of 0-10
    scale = min(10, int((connection_count / max_connections) * 10))
    
    # Create a dynamic indicator based on connection count
    if scale == 0:
        indicator = f"{Colors.FG_GREEN}◯{Colors.RESET} No active connections"
    else:
        # Create a pulsing/animated indicator
        pulse = int(time.time() * 2) % 2  # Alternates between 0 and 1
        
        if scale <= 3:
            color = Colors.FG_GREEN
            indicator = "◉" if pulse else "◎"
        elif scale <= 7:
            color = Colors.FG_YELLOW
            indicator = "◉" if pulse else "◎"
        else:
            color = Colors.FG_RED
            indicator = "◉" if pulse else "◎"
            
        indicator = f"{color}{indicator}{Colors.RESET} {connection_count} active connections"
        
    return indicator

