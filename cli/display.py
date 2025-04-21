"""
Command-line display for real-time CPU monitoring.
"""
import os
import sys
import time
import signal
import threading
from typing import Dict, Any, List, Optional, Union, Callable

from system_metrics.providers.cpu_provider import EnhancedMacOSCPUDataProvider
from system_metrics.parsers.cpu_parser import EnhancedCPUDataParser
from system_metrics.cpu import EnhancedCPUMonitor
from system_metrics.realtime.events import (
    MetricUpdateEvent, MetricEvent, Observer, MetricsEventDispatcher
)
from system_metrics.alerts.thresholds import CPUThresholdMonitor
from cli.formatting import (
    Colors, clear_screen, move_cursor, save_cursor_position, restore_cursor_position,
    format_overall_cpu, format_load_average, create_cpu_table, create_processes_table,
    get_terminal_size
)


class CPUDisplayManager:
    """
    Manages the real-time display of CPU information in the terminal.
    
    This class handles the rendering and updating of CPU usage information
    in a formatted CLI display.
    """
    
    def __init__(self, 
                cpu_monitor: Union[EnhancedCPUMonitor, Any],
                update_interval: float = 1.0,
                detailed_view: bool = True,
                enable_alerts: bool = True):
        """
        Initialize the display manager.
        
        Args:
            cpu_monitor: The CPU monitor instance
            update_interval: How often to update the display (seconds)
            detailed_view: Whether to show detailed CPU information
            enable_alerts: Whether to enable threshold alerts
        """
        self.cpu_monitor = cpu_monitor
        self.update_interval = update_interval
        self.detailed_view = detailed_view
        self.enable_alerts = enable_alerts
        
        self.running = False
        self.display_thread = None
        self.stop_event = threading.Event()
        
        # Setup threshold monitor if enabled
        self.threshold_monitor = None
        if self.enable_alerts:
            self.threshold_monitor = CPUThresholdMonitor(self.cpu_monitor)
            self.threshold_monitor.start()
        
        # Track history for CPU usage
        self.cpu_history: List[float] = []
        self.max_history_points = 100
        
        # Track active alerts
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        
        # Handle terminal resize
        self.terminal_width, self.terminal_height = get_terminal_size()
        self.setup_resize_handler()
        
        # Setup event listeners
        self.setup_event_listeners()
    
    def setup_resize_handler(self) -> None:
        """Set up handler for terminal resize events."""
        # Only works on Unix-like systems
        if hasattr(signal, 'SIGWINCH'):
            signal.signal(signal.SIGWINCH, self.handle_resize)
    
    def handle_resize(self, signum, frame) -> None:
        """Handle terminal resize event."""
        self.terminal_width, self.terminal_height = get_terminal_size()
    
    def setup_event_listeners(self) -> None:
        """Set up listeners for real-time metric events."""
        # Create event observer for alert events
        if self.enable_alerts:
            class AlertObserver(Observer[MetricEvent]):
                def __init__(self, display_manager):
                    self.display_manager = display_manager
                    
                def update(self, event: MetricEvent) -> None:
                    if event.event_type == MetricUpdateEvent.THRESHOLD_EXCEEDED:
                        # Store the alert with timestamp
                        alert_id = event.data.get('alert_type', 'unknown')
                        self.display_manager.add_active_alert(alert_id, event)
            
            # Register the observer
            self.alert_observer = AlertObserver(self)
            self.event_dispatcher = MetricsEventDispatcher()
            self.event_dispatcher.attach_with_filter(
                self.alert_observer, 
                [MetricUpdateEvent.THRESHOLD_EXCEEDED]
            )
            self.event_dispatcher.start()
    
    def add_active_alert(self, alert_id: str, event: MetricEvent) -> None:
        """
        Add an active alert to be displayed.
        
        Args:
            alert_id: Unique identifier for the alert
            event: The alert event data
        """
        self.active_alerts[alert_id] = {
            'message': event.message,
            'timestamp': event.timestamp,
            'data': event.data,
            'age': 0  # Will be updated in display loop
        }
    
    def update_alert_ages(self) -> None:
        """Update the age of active alerts and remove expired ones."""
        current_time = time.time()
        expired_alerts = []
        
        for alert_id, alert in self.active_alerts.items():
            alert['age'] = current_time - alert['timestamp']
            # Remove alerts older than 2 minutes
            if alert['age'] > 120:
                expired_alerts.append(alert_id)
        
        # Remove expired alerts
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
    
    def start(self) -> None:
        """Start the display loop."""
        if self.running:
            return
            
        self.running = True
        self.stop_event.clear()
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()
        
        # Start CPU monitor if it's not already running
        if hasattr(self.cpu_monitor, 'start') and not getattr(self.cpu_monitor, '_running', False):
            self.cpu_monitor.start()
    
    def stop(self) -> None:
        """Stop the display loop."""
        self.running = False
        self.stop_event.set()
        
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=self.update_interval + 1)
            self.display_thread = None
        
        # Stop threshold monitor if we started it
        if self.threshold_monitor:
            self.threshold_monitor.stop()
        
        # Stop event dispatcher
        if hasattr(self, 'event_dispatcher'):
            self.event_dispatcher.stop()
    
    def _display_loop(self) -> None:
        """Main display loop that updates the terminal."""
        try:
            # Hide cursor
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
            
            while self.running and not self.stop_event.is_set():
                try:
                    # Clear screen
                    clear_screen()
                    
                    # Render the display
                    self._render_display()
                    
                    # Wait for next update
                    if self.stop_event.wait(self.update_interval):
                        break
                        
                except Exception as e:
                    # Print error but continue running
                    sys.stderr.write(f"Error in display loop: {e}\n")
                    time.sleep(1)
                    
        finally:
            # Show cursor again
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
    
    def _render_display(self) -> None:
        """Render the complete CPU information display."""
        # Update alert ages
        if self.enable_alerts:
            self.update_alert_ages()
            
        # Get CPU data
        try:
            cpu_breakdown = self.cpu_monitor.get_overall_cpu_breakdown()
            cores = self.cpu_monitor.get_per_core_usage()
            processes = self.cpu_monitor.get_top_processes()
            
            # Get load average
            load_avg = [0.0, 0.0, 0.0]
            if hasattr(self.cpu_monitor, 'get_load_average'):
                load_avg = self.cpu_monitor.get_load_average()
            
            # Get CPU count
            cpu_count = len(cores)
            if hasattr(self.cpu_monitor, 'get_cpu_count'):
                cpu_count = self.cpu_monitor.get_cpu_count()
            
            # Track CPU history
            total_cpu = cpu_breakdown.get('user', 0) + cpu_breakdown.get('system', 0)
            self.cpu_history.append(total_cpu)
            if len(self.cpu_history) > self.max_history_points:
                self.cpu_history = self.cpu_history[-self.max_history_points:]
                
            # Display header with overall information
            self._render_header(cpu_breakdown, load_avg, cpu_count)
            
            # Display active alerts if any
            if self.active_alerts and self.enable_alerts:
                self._render_alerts()
                print()  # Empty line after alerts
            
            # Display CPU cores
            print(create_cpu_table(cores, show_detail=self.detailed_view))
            print()  # Empty line
            
            # Display top processes
            print(f"{Colors.BOLD}Top CPU Processes:{Colors.RESET}")
            print(create_processes_table(processes, max_processes=8))
            
        except Exception as e:
            # Display error
            print(f"{Colors.FG_RED}Error rendering display: {e}{Colors.RESET}")
    
    def _render_header(self, 
                      cpu_breakdown: Dict[str, float],
                      load_avg: List[float],
                      cpu_count: int) -> None:
        """
        Render the header with overall CPU information.
        
        Args:
            cpu_breakdown: Dictionary with user/system/idle percentages
            load_avg: List of load averages [1min, 5min, 15min]
            cpu_count: Number of CPU cores
        """
        # Format timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        # Print title and timestamp
        print(f"{Colors.BOLD}macOS CPU Monitor{Colors.RESET}                                {Colors.DIM}{timestamp}{Colors.RESET}")
        print()
        
        # Overall CPU usage
        user = cpu_breakdown.get('user', 0)
        system = cpu_breakdown.get('system', 0)
        idle = cpu_breakdown.get('idle', 0)
        
        print(format_overall_cpu(user, system, idle, width=40))
        
        # Load average
        if len(load_avg) >= 3:
            print(format_load_average(load_avg[0], load_avg[1], load_avg[2], cpu_count))
        
        print()  # Empty line
    
    def _render_alerts(self) -> None:
        """Render active alerts."""
        if not self.active_alerts:
            return
            
        print(f"\n{Colors.BOLD}{Colors.FG_YELLOW}Active Alerts:{Colors.RESET}")
        
        for alert_id, alert in self.active_alerts.items():
            age_mins = alert['age'] / 60
            age_str = f"{age_mins:.1f} minutes ago"
            
            severity = alert['data'].get('severity', 'WARNING')
            if severity == 'CRITICAL':
                color = Colors.FG_RED
            else:
                color = Colors.FG_YELLOW
                
            print(f" {color}• {alert['message']}{Colors.RESET} ({Colors.DIM}{age_str}{Colors.RESET})")


def run_cpu_monitor(update_interval: float = 1.0,
                   detailed_view: bool = True,
                   enable_alerts: bool = True) -> None:
    """
    Run the CPU monitor with real-time CLI display.
    
    Args:
        update_interval: How often to update the display (seconds)
        detailed_view: Whether to show detailed CPU information
        enable_alerts: Whether to enable threshold alerts
    """
    try:
        # Create the CPU monitor components
        provider = EnhancedMacOSCPUDataProvider()
        parser = EnhancedCPUDataParser()
        cpu_monitor = EnhancedCPUMonitor(provider, parser, update_interval=update_interval/2)
        
        # Create display manager
        display_manager = CPUDisplayManager(
            cpu_monitor=cpu_monitor,
            update_interval=update_interval,
            detailed_view=detailed_view,
            enable_alerts=enable_alerts
        )
        
        # Start display
        display_manager.start()
        
        # Wait for Ctrl+C
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping CPU monitor...")
        
        # Cleanup
        display_manager.stop()
        cpu_monitor.stop()
        
    except Exception as e:
        print(f"Error running CPU monitor: {e}")
