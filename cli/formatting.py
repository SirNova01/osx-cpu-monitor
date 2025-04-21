"""
Terminal formatting utilities for displaying CPU metrics.
"""
import os
import sys
import math
from typing import Dict, List, Any, Optional, Tuple, Union


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"

    # Foreground colors
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"
    FG_DEFAULT = "\033[39m"

    # Bright foreground colors
    FG_BRIGHT_BLACK = "\033[90m"
    FG_BRIGHT_RED = "\033[91m"
    FG_BRIGHT_GREEN = "\033[92m"
    FG_BRIGHT_YELLOW = "\033[93m"
    FG_BRIGHT_BLUE = "\033[94m"
    FG_BRIGHT_MAGENTA = "\033[95m"
    FG_BRIGHT_CYAN = "\033[96m"
    FG_BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_DEFAULT = "\033[49m"

    # Bright background colors
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"


def get_terminal_size() -> Tuple[int, int]:
    """
    Get the width and height of the terminal.
    
    Returns:
        Tuple of (columns, rows)
    """
    try:
        columns, rows = os.get_terminal_size(0)
        return columns, rows
    except (OSError, AttributeError):
        # Default to 80x24 if unable to determine
        return 80, 24


def create_progress_bar(
    value: float,
    max_value: float = 100.0,
    width: int = 20,
    char_empty: str = "▱",
    char_filled: str = "▰",
    color_gradient: bool = True,
) -> str:
    """
    Create a progress bar representation.
    
    Args:
        value: Current value (0-100)
        max_value: Maximum value
        width: Width of the progress bar in characters
        char_empty: Character for empty portion
        char_filled: Character for filled portion
        color_gradient: Whether to use color gradient based on value
        
    Returns:
        Progress bar string with ANSI colors
    """
    # Calculate the filled width
    percentage = min(1.0, value / max_value)
    filled_width = math.floor(percentage * width)
    empty_width = width - filled_width
    
    # Determine color based on value
    if color_gradient:
        if percentage <= 0.3:
            color = Colors.FG_GREEN
        elif percentage <= 0.7:
            color = Colors.FG_YELLOW
        else:
            color = Colors.FG_RED
    else:
        color = Colors.FG_CYAN
        
    # Create the progress bar
    filled_part = color + char_filled * filled_width
    empty_part = Colors.FG_BRIGHT_BLACK + char_empty * empty_width
    
    return f"{filled_part}{empty_part}{Colors.RESET}"


def create_histogram_bar(
    values: List[float],
    max_value: float = 100.0,
    width: int = 40,
    chars: List[str] = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"],
) -> str:
    """
    Create a histogram-style bar with varying heights.
    
    Args:
        values: List of values to plot
        max_value: Maximum value
        width: Width of the histogram
        chars: Characters to use for different heights
        
    Returns:
        Histogram string with ANSI colors
    """
    # If values list is too long, sample it to fit width
    if len(values) > width:
        # Simple sampling - take evenly spaced elements
        step = len(values) / width
        sampled_values = [values[min(len(values) - 1, int(i * step))] for i in range(width)]
    else:
        # If we have fewer values than width, repeat the last value
        sampled_values = values + [values[-1]] * (width - len(values)) if values else [0] * width
    
    # Normalize values to 0-1 range
    normalized_values = [min(1.0, val / max_value) for val in sampled_values]
    
    # Map normalized values to characters
    num_chars = len(chars)
    result = ""
    
    for val in normalized_values:
        char_index = min(num_chars - 1, int(val * num_chars))
        
        # Color based on value
        if val <= 0.3:
            color = Colors.FG_GREEN
        elif val <= 0.7:
            color = Colors.FG_YELLOW
        else:
            color = Colors.FG_RED
            
        result += color + chars[char_index]
        
    return result + Colors.RESET


def format_cpu_bar(usage: float, width: int = 20) -> str:
    """
    Create a color-coded CPU usage bar.
    
    Args:
        usage: CPU usage percentage (0-100)
        width: Width of the bar
        
    Returns:
        Formatted progress bar string
    """
    return create_progress_bar(usage, 100.0, width)


def format_cpu_user_system_bar(
    user: float, system: float, width: int = 30
) -> str:
    """
    Create a stacked bar showing user and system CPU usage.
    
    Args:
        user: User CPU percentage
        system: System CPU percentage
        width: Total width of the bar
        
    Returns:
        Stacked bar with user and system portions colored differently
    """
    total = user + system
    user_width = int((user / 100.0) * width) if total > 0 else 0
    system_width = int((system / 100.0) * width) if total > 0 else 0
    
    # Ensure at least one character if there's any usage
    if user > 0 and user_width == 0:
        user_width = 1
    if system > 0 and system_width == 0:
        system_width = 1
        
    # Adjust if sum exceeds width
    if user_width + system_width > width:
        excess = (user_width + system_width) - width
        # Remove from the larger portion first
        if user_width >= system_width:
            user_width -= excess
        else:
            system_width -= excess
    
    empty_width = width - (user_width + system_width)
    
    # Create the colored bar segments
    user_part = Colors.BG_BLUE + " " * user_width if user_width > 0 else ""
    system_part = Colors.BG_RED + " " * system_width if system_width > 0 else ""
    empty_part = Colors.BG_BRIGHT_BLACK + " " * empty_width if empty_width > 0 else ""
    
    return f"{user_part}{system_part}{empty_part}{Colors.RESET}"


def format_core_usage(
    core_id: int,
    usage: float,
    user: float,
    system: float,
    idle: float,
    frequency_mhz: Optional[float] = None,
    width: int = 20,
    show_detail: bool = True,
) -> str:
    """
    Format CPU core usage for display.
    
    Args:
        core_id: Core ID number
        usage: Total CPU usage percentage
        user: User CPU percentage
        system: System CPU percentage
        idle: Idle CPU percentage
        frequency_mhz: Core frequency in MHz (optional)
        width: Width of the progress bar
        show_detail: Whether to show detailed breakdown
        
    Returns:
        Formatted string with core usage information and bar
    """
    # Format the core identifier
    core_label = f"Core {core_id:2d}"
    
    if show_detail:
        # Format with detailed breakdown
        if frequency_mhz is not None:
            freq_str = f"{frequency_mhz:.0f} MHz"
            detail = f"{Colors.FG_CYAN}{usage:5.1f}%{Colors.RESET} (U:{user:4.1f}% S:{system:4.1f}% I:{idle:4.1f}%) @ {freq_str}"
        else:
            detail = f"{Colors.FG_CYAN}{usage:5.1f}%{Colors.RESET} (U:{user:4.1f}% S:{system:4.1f}% I:{idle:4.1f}%)"
            
        # Create progress bar
        bar = format_cpu_bar(usage, width)
        
        return f"{Colors.BOLD}{core_label}{Colors.RESET}: {bar} {detail}"
    else:
        # Simplified format
        if usage >= 75:
            color = Colors.FG_RED
        elif usage >= 50:
            color = Colors.FG_YELLOW
        else:
            color = Colors.FG_GREEN
            
        usage_str = f"{color}{usage:5.1f}%{Colors.RESET}"
        
        # Create progress bar
        bar = format_cpu_bar(usage, width)
        
        return f"{Colors.BOLD}{core_label}{Colors.RESET}: {bar} {usage_str}"


def format_process_usage(
    pid: int,
    cpu_percent: float,
    command: str,
    max_command_length: int = 30,
    width: int = 15,
) -> str:
    """
    Format process CPU usage for display.
    
    Args:
        pid: Process ID
        cpu_percent: CPU usage percentage
        command: Process command/name
        max_command_length: Maximum length for command truncation
        width: Width of the progress bar
        
    Returns:
        Formatted string with process usage information
    """
    # Truncate command if needed
    if len(command) > max_command_length:
        command = command[:max_command_length - 3] + "..."
    else:
        command = command.ljust(max_command_length)
    
    # Format PID and CPU percentage
    if cpu_percent >= 50:
        color = Colors.FG_RED
    elif cpu_percent >= 25:
        color = Colors.FG_YELLOW
    else:
        color = Colors.FG_GREEN
        
    pid_str = f"{pid:6d}"
    cpu_str = f"{color}{cpu_percent:5.1f}%{Colors.RESET}"
    
    # Create progress bar
    bar = format_cpu_bar(cpu_percent, width)
    
    return f"{pid_str} {command} {bar} {cpu_str}"


def format_overall_cpu(
    user: float,
    system: float,
    idle: float,
    width: int = 30,
) -> str:
    """
    Format overall CPU usage with a stacked bar.
    
    Args:
        user: User CPU percentage
        system: System CPU percentage
        idle: Idle CPU percentage
        width: Width of the bar
        
    Returns:
        Formatted string with overall CPU information and stacked bar
    """
    total = user + system
    
    # Format label and percentages
    if total >= 75:
        color = Colors.FG_RED
    elif total >= 50:
        color = Colors.FG_YELLOW
    else:
        color = Colors.FG_GREEN
        
    label = f"{Colors.BOLD}CPU Usage{Colors.RESET}:"
    cpu_str = f"{color}{total:5.1f}%{Colors.RESET} (User: {user:.1f}% Sys: {system:.1f}% Idle: {idle:.1f}%)"
    
    # Create stacked bar
    bar = format_cpu_user_system_bar(user, system, width)
    
    return f"{label} {bar} {cpu_str}"


def format_memory_usage(
    used: float,
    total: float,
    width: int = 25,
) -> str:
    """
    Format memory usage with a progress bar.
    
    Args:
        used: Used memory in bytes
        total: Total memory in bytes
        width: Width of the progress bar
        
    Returns:
        Formatted string with memory information and bar
    """
    # Convert to more readable units
    label = f"{Colors.BOLD}Memory{Colors.RESET}   :"
    
    if total >= 1024 * 1024 * 1024:  # Display in GB
        used_gb = used / (1024 * 1024 * 1024)
        total_gb = total / (1024 * 1024 * 1024)
        mem_str = f"{used_gb:.1f} GB / {total_gb:.1f} GB"
    else:  # Display in MB
        used_mb = used / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        mem_str = f"{used_mb:.1f} MB / {total_mb:.1f} MB"
    
    # Calculate percentage
    percentage = (used / total) * 100 if total > 0 else 0
    
    if percentage >= 90:
        color = Colors.FG_RED
    elif percentage >= 70:
        color = Colors.FG_YELLOW
    else:
        color = Colors.FG_GREEN
        
    percent_str = f"{color}{percentage:.1f}%{Colors.RESET}"
    
    # Create progress bar
    bar = create_progress_bar(percentage, 100, width)
    
    return f"{label} {bar} {percent_str} {mem_str}"


def format_load_average(
    load_1min: float,
    load_5min: float,
    load_15min: float,
    cpu_count: int,
) -> str:
    """
    Format system load average.
    
    Args:
        load_1min: 1-minute load average
        load_5min: 5-minute load average
        load_15min: 15-minute load average
        cpu_count: Number of CPU cores
        
    Returns:
        Formatted string with load average information
    """
    label = f"{Colors.BOLD}Load Avg{Colors.RESET} :"
    
    # Color code based on load relative to CPU count
    def color_load(load: float) -> str:
        ratio = load / cpu_count if cpu_count > 0 else load
        if ratio >= 1.0:
            color = Colors.FG_RED
        elif ratio >= 0.7:
            color = Colors.FG_YELLOW
        else:
            color = Colors.FG_GREEN
        return f"{color}{load:.2f}{Colors.RESET}"
    
    load_str = f"{color_load(load_1min)} (1m), {color_load(load_5min)} (5m), {color_load(load_15min)} (15m)"
    
    return f"{label} {load_str}"


def create_cpu_table(
    cores_data: List[Dict[str, Any]],
    max_width: int = 80,
    show_detail: bool = True,
) -> str:
    """
    Create a formatted table of CPU core information.
    
    Args:
        cores_data: List of core data dictionaries
        max_width: Maximum width of the output
        show_detail: Whether to show detailed core information
        
    Returns:
        Formatted table as a string
    """
    # Determine available width
    term_width, _ = get_terminal_size()
    width = min(term_width, max_width)
    
    # Calculate bar width based on available space
    bar_width = width - 60 if show_detail else width - 25
    bar_width = max(10, bar_width)  # Ensure minimum width
    
    # Create header
    header = f"{Colors.BOLD}{'Core':6s} {'Usage':6s} {'Bar':{bar_width}s}"
    if show_detail:
        header += f" {'User':5s} {'Sys':5s} {'Idle':5s} {'Freq':10s}"
    header += f"{Colors.RESET}"
    
    # Create rows
    rows = []
    for core in cores_data:
        core_id = core.get('core_id', 0)
        usage = core.get('usage', 0.0)
        user = core.get('user', 0.0)
        system = core.get('system', 0.0)
        idle = core.get('idle', 0.0)
        freq = core.get('frequency_mhz')
        
        row = format_core_usage(
            core_id=core_id,
            usage=usage,
            user=user,
            system=system,
            idle=idle,
            frequency_mhz=freq,
            width=bar_width,
            show_detail=show_detail
        )
        rows.append(row)
    
    # Combine header and rows
    divider = "─" * width
    return f"{header}\n{Colors.FG_BRIGHT_BLACK}{divider}{Colors.RESET}\n" + "\n".join(rows)


def create_processes_table(
    processes: List[Dict[str, Any]],
    max_width: int = 80,
    max_processes: int = 10,
) -> str:
    """
    Create a formatted table of top CPU-consuming processes.
    
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
    cmd_width = width - 45
    cmd_width = max(15, cmd_width)  # Ensure minimum width
    
    bar_width = 15
    
    # Create header
    header = f"{Colors.BOLD}{'PID':6s} {'Command':{cmd_width}s} {'CPU Usage':{bar_width+8}s}{Colors.RESET}"
    
    # Create rows
    rows = []
    for i, proc in enumerate(processes):
        if i >= max_processes:
            break
            
        pid = proc.get('pid', 0)
        cpu_percent = proc.get('cpu_percent', 0.0)
        command = proc.get('command', 'unknown')
        
        row = format_process_usage(
            pid=pid,
            cpu_percent=cpu_percent,
            command=command,
            max_command_length=cmd_width,
            width=bar_width
        )
        rows.append(row)
    
    # Combine header and rows
    divider = "─" * width
    return f"{header}\n{Colors.FG_BRIGHT_BLACK}{divider}{Colors.RESET}\n" + "\n".join(rows)


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def move_cursor(row: int, col: int) -> None:
    """
    Move the cursor to a specific position in the terminal.
    
    Args:
        row: Row number (1-based)
        col: Column number (1-based)
    """
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def save_cursor_position() -> None:
    """Save the current cursor position."""
    sys.stdout.write("\033[s")
    sys.stdout.flush()


def restore_cursor_position() -> None:
    """Restore the saved cursor position."""
    sys.stdout.write("\033[u")
    sys.stdout.flush()


def create_color_gradient(value: float, min_val: float, max_val: float) -> str:
    """
    Create a color gradient based on a value.
    
    Args:
        value: Current value
        min_val: Minimum value in range
        max_val: Maximum value in range
        
    Returns:
        ANSI color code
    """
    # Normalize to 0-1 range
    norm_val = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
    norm_val = max(0, min(1, norm_val))  # Clamp to 0-1
    
    # Convert to HSL-like space where:
    # hue 0.33 (120 degrees) = green
    # hue 0.17 (60 degrees) = yellow
    # hue 0.0 (0 degrees) = red
    hue = 0.33 * (1 - norm_val)
    
    # Convert HSL to RGB
    def hue_to_rgb(h):
        h *= 6
        section = int(h)
        remainder = h - section
        
        if section == 0 or section == 6:
            r, g, b = 1, remainder, 0
        elif section == 1:
            r, g, b = 1 - remainder, 1, 0
        elif section == 2:
            r, g, b = 0, 1, remainder
        elif section == 3:
            r, g, b = 0, 1 - remainder, 1
        elif section == 4:
            r, g, b = remainder, 0, 1
        else:  # section == 5
            r, g, b = 1, 0, 1 - remainder
        
        return r, g, b
    
    r, g, b = hue_to_rgb(hue * 3)  # Multiply by 3 to only use green-yellow-red range
    
    # Convert to 0-255 range
    r = int(r * 255)
    g = int(g * 255)
    b = int(b * 255)
    
    # Return true color ANSI code
    return f"\033[38;2;{r};{g};{b}m"
