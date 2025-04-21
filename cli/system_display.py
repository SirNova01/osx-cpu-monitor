# # """
# # Command-line display for real-time system monitoring (CPU and Network).
# # """
# # import os
# # import sys
# # import time
# # import signal
# # import threading
# # from typing import Dict, List, Any, Optional, Union, Callable

# # from system_metrics.alerts.network_thresholds import NetworkThresholdMonitor
# # from system_metrics.providers.cpu_provider import EnhancedMacOSCPUDataProvider
# # from system_metrics.providers.network_provider import EnhancedMacOSNetworkDataProvider
# # from system_metrics.parsers.cpu_parser import EnhancedCPUDataParser
# # from system_metrics.parsers.network_parser import MacOSNetworkParser
# # from system_metrics.cpu import EnhancedCPUMonitor
# # from system_metrics.network import EnhancedNetworkMonitor
# # from system_metrics.alerts.thresholds import CPUThresholdMonitor
# # from system_metrics.realtime.events import (
# #     MetricUpdateEvent, MetricEvent, Observer, MetricsEventDispatcher
# # )

# # from cli.display import CPUDisplayManager
# # from cli.formatting import (
# #     Colors, clear_screen, move_cursor, save_cursor_position, restore_cursor_position,
# #     format_overall_cpu, format_load_average, create_cpu_table, create_processes_table,
# #     get_terminal_size
# # )
# # from cli.network_formatting import (
# #     format_bandwidth, format_data_transferred, create_interfaces_table, 
# #     create_network_processes_table, create_connections_summary, create_wifi_summary
# # )


# # class SystemDisplayManager(CPUDisplayManager):
# #     """
# #     Manages the real-time display of system information in the terminal.
    
# #     This class extends the CPUDisplayManager to also display network information.
# #     """
    
# #     def __init__(self, 
# #                 cpu_monitor: Union[EnhancedCPUMonitor, Any],
# #                 network_monitor: Optional[Union[EnhancedNetworkMonitor, Any]] = None,
# #                 update_interval: float = 1.0,
# #                 detailed_view: bool = True,
# #                 enable_alerts: bool = True,
# #                 show_cpu: bool = True,
# #                 show_network: bool = True):
# #         """
# #         Initialize the system display manager.
        
# #         Args:
# #             cpu_monitor: The CPU monitor instance
# #             network_monitor: The network monitor instance
# #             update_interval: How often to update the display (seconds)
# #             detailed_view: Whether to show detailed information
# #             enable_alerts: Whether to enable threshold alerts
# #             show_cpu: Whether to show CPU information
# #             show_network: Whether to show network information
# #         """
# #         # Call the parent constructor
# #         super().__init__(
# #             cpu_monitor=cpu_monitor,
# #             update_interval=update_interval,
# #             detailed_view=detailed_view,
# #             enable_alerts=enable_alerts
# #         )
        
# #         # Add network-specific properties
# #         self.network_monitor = network_monitor
# #         self.show_cpu = show_cpu
# #         self.show_network = show_network
        
# #         # Setup network threshold monitor if enabled
# #         self.network_threshold_monitor = None
# #         if self.enable_alerts and self.network_monitor and self.show_network:
# #             self.network_threshold_monitor = NetworkThresholdMonitor(self.network_monitor)
# #             self.network_threshold_monitor.start()
        
# #         # Track history for network bandwidth usage
# #         self.rx_history: List[float] = []
# #         self.tx_history: List[float] = []
# #         self.max_history_points = 100
        
# #         # Setup additional event listeners for network alerts
# #         if self.show_network:
# #             self.setup_network_event_listeners()
    
# #     def setup_network_event_listeners(self) -> None:
# #         """Set up listeners for real-time network metric events."""
# #         # Create event observer for network alert events
# #         if self.enable_alerts and self.network_monitor:
# #             class NetworkAlertObserver(Observer[MetricEvent]):
# #                 def __init__(self, display_manager):
# #                     self.display_manager = display_manager
                    
# #                 def update(self, event: MetricEvent) -> None:
# #                     if event.event_type == MetricUpdateEvent.THRESHOLD_EXCEEDED:
# #                         # Store the alert with timestamp
# #                         alert_id = f"network_{event.data.get('alert_type', 'unknown')}"
# #                         self.display_manager.add_active_alert(alert_id, event)
            
# #             # Register the observer
# #             self.network_alert_observer = NetworkAlertObserver(self)
# #             self.event_dispatcher.attach_with_filter(
# #                 self.network_alert_observer, 
# #                 [MetricUpdateEvent.THRESHOLD_EXCEEDED]
# #             )
    
# #     def stop(self) -> None:
# #         """Stop the display loop and all monitors."""
# #         super().stop()
        
# #         # Stop network threshold monitor if we started it
# #         if self.network_threshold_monitor:
# #             self.network_threshold_monitor.stop()
    
# #     def _render_display(self) -> None:
# #         """Render the complete system information display."""
# #         # Update alert ages
# #         if self.enable_alerts:
# #             self.update_alert_ages()
            
# #         try:
# #             # Determine rendering order based on configuration
# #             sections = []
# #             if self.show_cpu:
# #                 sections.append(self._render_cpu_section)
# #             if self.show_network:
# #                 sections.append(self._render_network_section)
            
# #             # Display header with timestamp
# #             timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
# #             title = "macOS System Monitor"
# #             print(f"{Colors.BOLD}{title}{Colors.RESET}                              {Colors.DIM}{timestamp}{Colors.RESET}")
# #             print()
            
# #             # Display active alerts if any
# #             if self.active_alerts and self.enable_alerts:
# #                 self._render_alerts()
# #                 print()  # Empty line after alerts
            
# #             # Render each section
# #             for i, render_func in enumerate(sections):
# #                 render_func()
# #                 if i < len(sections) - 1:
# #                     print("\n" + "─" * 80 + "\n")  # Section divider
            
# #         except Exception as e:
# #             # Display error
# #             print(f"{Colors.FG_RED}Error rendering display: {e}{Colors.RESET}")
    
# #     def _render_cpu_section(self) -> None:
# #         """Render the CPU information section."""
# #         try:
# #             # Get CPU data
# #             cpu_breakdown = self.cpu_monitor.get_overall_cpu_breakdown()
# #             cores = self.cpu_monitor.get_per_core_usage()
# #             processes = self.cpu_monitor.get_top_processes()
            
# #             # Get load average
# #             load_avg = [0.0, 0.0, 0.0]
# #             if hasattr(self.cpu_monitor, 'get_load_average'):
# #                 load_avg = self.cpu_monitor.get_load_average()
            
# #             # Get CPU count
# #             cpu_count = len(cores)
# #             if hasattr(self.cpu_monitor, 'get_cpu_count'):
# #                 cpu_count = self.cpu_monitor.get_cpu_count()
            
# #             # Track CPU history
# #             total_cpu = cpu_breakdown.get('user', 0) + cpu_breakdown.get('system', 0)
# #             self.cpu_history.append(total_cpu)
# #             if len(self.cpu_history) > self.max_history_points:
# #                 self.cpu_history = self.cpu_history[-self.max_history_points:]
                
# #             # Display CPU header with overall information
# #             print(f"{Colors.BOLD}CPU Information{Colors.RESET}")
# #             print()
            
# #             # Overall CPU usage
# #             user = cpu_breakdown.get('user', 0)
# #             system = cpu_breakdown.get('system', 0)
# #             idle = cpu_breakdown.get('idle', 0)
            
# #             print(format_overall_cpu(user, system, idle, width=40))
            
# #             # Load average
# #             if len(load_avg) >= 3:
# #                 print(format_load_average(load_avg[0], load_avg[1], load_avg[2], cpu_count))
            
# #             print()  # Empty line
            
# #             # Display CPU cores
# #             print(create_cpu_table(cores, show_detail=self.detailed_view))
# #             print()  # Empty line
            
# #             # Display top processes
# #             print(f"{Colors.BOLD}Top CPU Processes:{Colors.RESET}")
# #             print(create_processes_table(processes, max_processes=5))
            
# #         except Exception as e:
# #             print(f"{Colors.FG_RED}Error rendering CPU section: {e}{Colors.RESET}")
    
# #     def _render_network_section(self) -> None:
# #         """Render the network information section."""
# #         try:
# #             if not self.network_monitor:
# #                 print(f"{Colors.FG_YELLOW}Network monitoring is not available.{Colors.RESET}")
# #                 return
                
# #             # Get network data
# #             bandwidth_usage = self.network_monitor.get_bandwidth_usage()
# #             rx_bytes_per_sec = bandwidth_usage.get("rx_bytes_per_sec", 0)
# #             tx_bytes_per_sec = bandwidth_usage.get("tx_bytes_per_sec", 0)
            
# #             interfaces = self.network_monitor.get_interface_details()
            
# #             # Get connection statistics if available
# #             connection_stats = {}
# #             if hasattr(self.network_monitor, "get_connection_stats"):
# #                 connection_stats = self.network_monitor.get_connection_stats()
            
# #             # Get WiFi details if available
# #             wifi_details = {}
# #             if hasattr(self.network_monitor, "get_wifi_details"):
# #                 wifi_details = self.network_monitor.get_wifi_details()
            
# #             # Get top network processes if available
# #             network_processes = []
# #             if hasattr(self.network_monitor, "get_network_processes"):
# #                 network_processes = self.network_monitor.get_network_processes()
            
# #             # Track bandwidth history
# #             self.rx_history.append(rx_bytes_per_sec)
# #             self.tx_history.append(tx_bytes_per_sec)
# #             if len(self.rx_history) > self.max_history_points:
# #                 self.rx_history = self.rx_history[-self.max_history_points:]
# #                 self.tx_history = self.tx_history[-self.max_history_points:]
            
# #             # Display network header
# #             print(f"{Colors.BOLD}Network Information{Colors.RESET}")
# #             print()
            
# #             # Display bandwidth usage
# #             print(format_bandwidth(rx_bytes_per_sec, tx_bytes_per_sec, width=40))
# #             print()
            
# #             # Display total data transferred
# #             total_rx = 0
# #             total_tx = 0
            
# #             # Sum up data from all interfaces
# #             for interface in interfaces:
# #                 total_rx += interface.get("rx_bytes", 0)
# #                 total_tx += interface.get("tx_bytes", 0)
            
# #             print(format_data_transferred(total_rx, total_tx))
# #             print()
            
# #             # Display connection summary if available
# #             if connection_stats:
# #                 print(create_connections_summary(connection_stats))
# #                 print()
            
# #             # Display WiFi summary if connected
# #             if wifi_details and wifi_details.get("connected", False):
# #                 wifi_summary = create_wifi_summary(wifi_details)
# #                 if wifi_summary:
# #                     print(wifi_summary)
# #                     print()
            
# #             # Display network interfaces
# #             print(f"{Colors.BOLD}Network Interfaces:{Colors.RESET}")
# #             print(create_interfaces_table(interfaces, include_inactive=False))
# #             print()
            
# #             # Display top network processes if available
# #             if network_processes:
# #                 print(f"{Colors.BOLD}Top Network Processes:{Colors.RESET}")
# #                 print(create_network_processes_table(network_processes, max_processes=5))
            
# #         except Exception as e:
# #             print(f"{Colors.FG_RED}Error rendering network section: {e}{Colors.RESET}")


# # def run_system_monitor(update_interval: float = 1.0,
# #                     detailed_view: bool = True,
# #                     enable_alerts: bool = True,
# #                     show_cpu: bool = True,
# #                     show_network: bool = True) -> None:
# #     """
# #     Run the system monitor with real-time CLI display.
    
# #     Args:
# #         update_interval: How often to update the display (seconds)
# #         detailed_view: Whether to show detailed information
# #         enable_alerts: Whether to enable threshold alerts
# #         show_cpu: Whether to show CPU information
# #         show_network: Whether to show network information
# #     """
# #     try:
# #         # Create the CPU monitor components
# #         cpu_monitor = None
# #         network_monitor = None
        
# #         if show_cpu:
# #             cpu_provider = EnhancedMacOSCPUDataProvider()
# #             cpu_parser = EnhancedCPUDataParser()
# #             cpu_monitor = EnhancedCPUMonitor(cpu_provider, cpu_parser, update_interval=update_interval/2)
# #             cpu_monitor.start()
        
# #         if show_network:
# #             network_provider = EnhancedMacOSNetworkDataProvider()
# #             network_parser = MacOSNetworkParser()
# #             network_monitor = EnhancedNetworkMonitor(network_provider, network_parser, update_interval=update_interval/2)
# #             network_monitor.start()
        
# #         # Create display manager
# #         display_manager = SystemDisplayManager(
# #             cpu_monitor=cpu_monitor,
# #             network_monitor=network_monitor,
# #             update_interval=update_interval,
# #             detailed_view=detailed_view,
# #             enable_alerts=enable_alerts,
# #             show_cpu=show_cpu,
# #             show_network=show_network
# #         )
        
# #         # Start display
# #         display_manager.start()
        
# #         # Wait for Ctrl+C
# #         try:
# #             while True:
# #                 time.sleep(1)
# #         except KeyboardInterrupt:
# #             print("\nStopping system monitor...")
        
# #         # Cleanup
# #         display_manager.stop()
# #         if cpu_monitor:
# #             cpu_monitor.stop()
# #         if network_monitor:
# #             network_monitor.stop()
        
# #     except Exception as e:
# #         print(f"Error running system monitor: {e}")








# """
# Command-line display for real-time system monitoring (CPU and Network).
# """
# import os
# import sys
# import time
# import signal
# import threading
# from typing import Dict, List, Any, Optional, Union, Callable

# from system_metrics.providers.cpu_provider import EnhancedMacOSCPUDataProvider
# from system_metrics.providers.network_provider import EnhancedMacOSNetworkDataProvider
# from system_metrics.parsers.cpu_parser import EnhancedCPUDataParser
# from system_metrics.parsers.network_parser import MacOSNetworkParser
# from system_metrics.cpu import EnhancedCPUMonitor
# from system_metrics.network import EnhancedNetworkMonitor
# from system_metrics.alerts.thresholds import CPUThresholdMonitor
# from system_metrics.alerts.network_thresholds import NetworkThresholdMonitor
# from system_metrics.realtime.events import (
#     MetricUpdateEvent, MetricEvent, Observer, MetricsEventDispatcher
# )

# from cli.formatting import (
#     Colors, clear_screen, move_cursor, save_cursor_position, restore_cursor_position,
#     format_overall_cpu, format_load_average, create_cpu_table, create_processes_table,
#     get_terminal_size
# )
# from cli.network_formatting import (
#     format_bandwidth, format_data_transferred, create_interfaces_table, 
#     create_network_processes_table, create_connections_summary, create_wifi_summary
# )


# class SystemDisplayManager:
#     """
#     Manages the real-time display of system information in the terminal.
    
#     This class displays CPU and/or network information based on configuration.
#     """
    
#     def __init__(self, 
#                 cpu_monitor: Optional[EnhancedCPUMonitor] = None,
#                 network_monitor: Optional[EnhancedNetworkMonitor] = None,
#                 update_interval: float = 1.0,
#                 detailed_view: bool = True,
#                 enable_alerts: bool = True,
#                 show_cpu: bool = True,
#                 show_network: bool = True):
#         """
#         Initialize the system display manager.
        
#         Args:
#             cpu_monitor: The CPU monitor instance (can be None if CPU monitoring is disabled)
#             network_monitor: The network monitor instance (can be None if network monitoring is disabled)
#             update_interval: How often to update the display (seconds)
#             detailed_view: Whether to show detailed information
#             enable_alerts: Whether to enable threshold alerts
#             show_cpu: Whether to show CPU information
#             show_network: Whether to show network information
#         """
#         self.cpu_monitor = cpu_monitor
#         self.network_monitor = network_monitor
#         self.update_interval = update_interval
#         self.detailed_view = detailed_view
#         self.enable_alerts = enable_alerts
#         self.show_cpu = show_cpu and cpu_monitor is not None
#         self.show_network = show_network and network_monitor is not None
        
#         # Track history for metrics visualization
#         self.cpu_history: List[float] = []
#         self.rx_history: List[float] = []
#         self.tx_history: List[float] = []
#         self.max_history_points = 100
        
#         # Thread control
#         self.running = False
#         self.display_thread = None
#         self.stop_event = threading.Event()
        
#         # Initialize event dispatcher
#         self.event_dispatcher = MetricsEventDispatcher()
        
#         # Setup threshold monitors if enabled
#         self.cpu_threshold_monitor = None
#         self.network_threshold_monitor = None
        
#         if self.enable_alerts:
#             # Only create CPU threshold monitor if CPU monitoring is enabled
#             if self.show_cpu and self.cpu_monitor:
#                 self.cpu_threshold_monitor = CPUThresholdMonitor(self.cpu_monitor)
#                 self.cpu_threshold_monitor.start()
            
#             # Only create network threshold monitor if network monitoring is enabled
#             if self.show_network and self.network_monitor:
#                 self.network_threshold_monitor = NetworkThresholdMonitor(self.network_monitor)
#                 self.network_threshold_monitor.start()
        
#         # Track active alerts
#         self.active_alerts: Dict[str, Dict[str, Any]] = {}
        
#         # Handle terminal resize
#         self.terminal_width, self.terminal_height = get_terminal_size()
#         self.setup_resize_handler()
        
#         # Setup event listeners
#         self.setup_event_listeners()
    
#     def setup_resize_handler(self) -> None:
#         """Set up handler for terminal resize events."""
#         # Only works on Unix-like systems
#         if hasattr(signal, 'SIGWINCH'):
#             signal.signal(signal.SIGWINCH, self.handle_resize)
    
#     def handle_resize(self, signum, frame) -> None:
#         """Handle terminal resize event."""
#         self.terminal_width, self.terminal_height = get_terminal_size()
    
#     def setup_event_listeners(self) -> None:
#         """Set up listeners for real-time metric events."""
#         # Create event observer for alert events
#         if self.enable_alerts:
#             class AlertObserver(Observer[MetricEvent]):
#                 def __init__(self, display_manager):
#                     self.display_manager = display_manager
                    
#                 def update(self, event: MetricEvent) -> None:
#                     if event.event_type == MetricUpdateEvent.THRESHOLD_EXCEEDED:
#                         # Store the alert with timestamp
#                         alert_id = event.data.get('alert_type', 'unknown')
#                         self.display_manager.add_active_alert(alert_id, event)
            
#             # Register the observer
#             self.alert_observer = AlertObserver(self)
#             self.event_dispatcher.attach_with_filter(
#                 self.alert_observer, 
#                 [MetricUpdateEvent.THRESHOLD_EXCEEDED]
#             )
#             self.event_dispatcher.start()
    
#     def add_active_alert(self, alert_id: str, event: MetricEvent) -> None:
#         """
#         Add an active alert to be displayed.
        
#         Args:
#             alert_id: Unique identifier for the alert
#             event: The alert event data
#         """
#         self.active_alerts[alert_id] = {
#             'message': event.message,
#             'timestamp': event.timestamp,
#             'data': event.data,
#             'age': 0  # Will be updated in display loop
#         }
    
#     def update_alert_ages(self) -> None:
#         """Update the age of active alerts and remove expired ones."""
#         current_time = time.time()
#         expired_alerts = []
        
#         for alert_id, alert in self.active_alerts.items():
#             alert['age'] = current_time - alert['timestamp']
#             # Remove alerts older than 2 minutes
#             if alert['age'] > 120:
#                 expired_alerts.append(alert_id)
        
#         # Remove expired alerts
#         for alert_id in expired_alerts:
#             del self.active_alerts[alert_id]
    
#     def start(self) -> None:
#         """Start the display loop."""
#         if self.running:
#             return
            
#         self.running = True
#         self.stop_event.clear()
#         self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
#         self.display_thread.start()
        
#         # Start CPU monitor if it's active
#         if self.show_cpu and self.cpu_monitor and hasattr(self.cpu_monitor, 'start') and not getattr(self.cpu_monitor, '_running', False):
#             self.cpu_monitor.start()
            
#         # Start network monitor if it's active
#         if self.show_network and self.network_monitor and hasattr(self.network_monitor, 'start') and not getattr(self.network_monitor, '_running', False):
#             self.network_monitor.start()
    
#     def stop(self) -> None:
#         """Stop the display loop and all monitors."""
#         self.running = False
#         self.stop_event.set()
        
#         if self.display_thread and self.display_thread.is_alive():
#             self.display_thread.join(timeout=self.update_interval + 1)
#             self.display_thread = None
        
#         # Stop threshold monitors if we started them
#         if self.cpu_threshold_monitor:
#             self.cpu_threshold_monitor.stop()
        
#         if self.network_threshold_monitor:
#             self.network_threshold_monitor.stop()
        
#         # Stop event dispatcher
#         if hasattr(self, 'event_dispatcher'):
#             self.event_dispatcher.stop()
    
#     def _display_loop(self) -> None:
#         """Main display loop that updates the terminal."""
#         try:
#             # Hide cursor
#             sys.stdout.write("\033[?25l")
#             sys.stdout.flush()
            
#             while self.running and not self.stop_event.is_set():
#                 try:
#                     # Clear screen
#                     clear_screen()
                    
#                     # Render the display
#                     self._render_display()
                    
#                     # Wait for next update
#                     if self.stop_event.wait(self.update_interval):
#                         break
                        
#                 except Exception as e:
#                     # Print error but continue running
#                     sys.stderr.write(f"Error in display loop: {e}\n")
#                     time.sleep(1)
                    
#         finally:
#             # Show cursor again
#             sys.stdout.write("\033[?25h")
#             sys.stdout.flush()
    
#     def _render_display(self) -> None:
#         """Render the complete system information display."""
#         # Update alert ages
#         if self.enable_alerts:
#             self.update_alert_ages()
            
#         try:
#             # Determine rendering order based on configuration
#             sections = []
#             if self.show_cpu:
#                 sections.append(self._render_cpu_section)
#             if self.show_network:
#                 sections.append(self._render_network_section)
            
#             # Display header with timestamp
#             timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
#             title = "macOS System Monitor"
#             print(f"{Colors.BOLD}{title}{Colors.RESET}                              {Colors.DIM}{timestamp}{Colors.RESET}")
#             print()
            
#             # Display active alerts if any
#             if self.active_alerts and self.enable_alerts:
#                 self._render_alerts()
#                 print()  # Empty line after alerts
            
#             # Render each section
#             for i, render_func in enumerate(sections):
#                 render_func()
#                 if i < len(sections) - 1:
#                     print("\n" + "─" * 80 + "\n")  # Section divider
            
#         except Exception as e:
#             # Display error
#             print(f"{Colors.FG_RED}Error rendering display: {e}{Colors.RESET}")
    
#     def _render_alerts(self) -> None:
#         """Render active alerts."""
#         if not self.active_alerts:
#             return
            
#         print(f"\n{Colors.BOLD}{Colors.FG_YELLOW}Active Alerts:{Colors.RESET}")
        
#         for alert_id, alert in self.active_alerts.items():
#             age_mins = alert['age'] / 60
#             age_str = f"{age_mins:.1f} minutes ago"
            
#             severity = alert['data'].get('severity', 'WARNING')
#             if severity == 'CRITICAL':
#                 color = Colors.FG_RED
#             else:
#                 color = Colors.FG_YELLOW
                
#             print(f" {color}• {alert['message']}{Colors.RESET} ({Colors.DIM}{age_str}{Colors.RESET})")
    
#     def _render_cpu_section(self) -> None:
#         """Render the CPU information section."""
#         try:
#             if not self.cpu_monitor:
#                 print(f"{Colors.FG_YELLOW}CPU monitoring is not available.{Colors.RESET}")
#                 return
                
#             # Get CPU data
#             cpu_breakdown = self.cpu_monitor.get_overall_cpu_breakdown()
#             cores = self.cpu_monitor.get_per_core_usage()
#             processes = self.cpu_monitor.get_top_processes()
            
#             # Get load average
#             load_avg = [0.0, 0.0, 0.0]
#             if hasattr(self.cpu_monitor, 'get_load_average'):
#                 load_avg = self.cpu_monitor.get_load_average()
            
#             # Get CPU count
#             cpu_count = len(cores)
#             if hasattr(self.cpu_monitor, 'get_cpu_count'):
#                 cpu_count = self.cpu_monitor.get_cpu_count()
            
#             # Track CPU history
#             total_cpu = cpu_breakdown.get('user', 0) + cpu_breakdown.get('system', 0)
#             self.cpu_history.append(total_cpu)
#             if len(self.cpu_history) > self.max_history_points:
#                 self.cpu_history = self.cpu_history[-self.max_history_points:]
                
#             # Display CPU header with overall information
#             print(f"{Colors.BOLD}CPU Information{Colors.RESET}")
#             print()
            
#             # Overall CPU usage
#             user = cpu_breakdown.get('user', 0)
#             system = cpu_breakdown.get('system', 0)
#             idle = cpu_breakdown.get('idle', 0)
            
#             print(format_overall_cpu(user, system, idle, width=40))
            
#             # Load average
#             if len(load_avg) >= 3:
#                 print(format_load_average(load_avg[0], load_avg[1], load_avg[2], cpu_count))
            
#             print()  # Empty line
            
#             # Display CPU cores
#             print(create_cpu_table(cores, show_detail=self.detailed_view))
#             print()  # Empty line
            
#             # Display top processes
#             print(f"{Colors.BOLD}Top CPU Processes:{Colors.RESET}")
#             print(create_processes_table(processes, max_processes=5))
            
#         except Exception as e:
#             print(f"{Colors.FG_RED}Error rendering CPU section: {e}{Colors.RESET}")
    
#     def _render_network_section(self) -> None:
#         """Render the network information section."""
#         try:
#             if not self.network_monitor:
#                 print(f"{Colors.FG_YELLOW}Network monitoring is not available.{Colors.RESET}")
#                 return
                
#             # Get network data
#             bandwidth_usage = self.network_monitor.get_bandwidth_usage()
#             rx_bytes_per_sec = bandwidth_usage.get("rx_bytes_per_sec", 0)
#             tx_bytes_per_sec = bandwidth_usage.get("tx_bytes_per_sec", 0)
            
#             interfaces = self.network_monitor.get_interface_details()
            
#             # Get connection statistics if available
#             connection_stats = {}
#             if hasattr(self.network_monitor, "get_connection_stats"):
#                 connection_stats = self.network_monitor.get_connection_stats()
            
#             # Get WiFi details if available
#             wifi_details = {}
#             if hasattr(self.network_monitor, "get_wifi_details"):
#                 wifi_details = self.network_monitor.get_wifi_details()
            
#             # Get top network processes if available
#             network_processes = []
#             if hasattr(self.network_monitor, "get_network_processes"):
#                 network_processes = self.network_monitor.get_network_processes()
            
#             # Track bandwidth history
#             self.rx_history.append(rx_bytes_per_sec)
#             self.tx_history.append(tx_bytes_per_sec)
#             if len(self.rx_history) > self.max_history_points:
#                 self.rx_history = self.rx_history[-self.max_history_points:]
#                 self.tx_history = self.tx_history[-self.max_history_points:]
            
#             # Display network header
#             print(f"{Colors.BOLD}Network Information{Colors.RESET}")
#             print()
            
#             # Display bandwidth usage
#             print(format_bandwidth(rx_bytes_per_sec, tx_bytes_per_sec, width=40))
#             print()
            
#             # Display total data transferred
#             total_rx = 0
#             total_tx = 0
            
#             # Sum up data from all interfaces
#             for interface in interfaces:
#                 total_rx += interface.get("rx_bytes", 0)
#                 total_tx += interface.get("tx_bytes", 0)
            
#             print(format_data_transferred(total_rx, total_tx))
#             print()
            
#             # Display connection summary if available
#             if connection_stats:
#                 print(create_connections_summary(connection_stats))
#                 print()
            
#             # Display WiFi summary if connected
#             if wifi_details and wifi_details.get("connected", False):
#                 wifi_summary = create_wifi_summary(wifi_details)
#                 if wifi_summary:
#                     print(wifi_summary)
#                     print()
            
#             # Display network interfaces
#             print(f"{Colors.BOLD}Network Interfaces:{Colors.RESET}")
#             print(create_interfaces_table(interfaces, include_inactive=False))
#             print()
            
#             # Display top network processes if available
#             if network_processes:
#                 print(f"{Colors.BOLD}Top Network Processes:{Colors.RESET}")
#                 print(create_network_processes_table(network_processes, max_processes=5))
            
#         except Exception as e:
#             print(f"{Colors.FG_RED}Error rendering network section: {e}{Colors.RESET}")


# def run_system_monitor(update_interval: float = 1.0,
#                     detailed_view: bool = True,
#                     enable_alerts: bool = True,
#                     show_cpu: bool = True,
#                     show_network: bool = True) -> None:
#     """
#     Run the system monitor with real-time CLI display.
    
#     Args:
#         update_interval: How often to update the display (seconds)
#         detailed_view: Whether to show detailed information
#         enable_alerts: Whether to enable threshold alerts
#         show_cpu: Whether to show CPU information
#         show_network: Whether to show network information
#     """
#     try:
#         # Create the monitors only for the selected components
#         cpu_monitor = None
#         network_monitor = None
        
#         if show_cpu:
#             cpu_provider = EnhancedMacOSCPUDataProvider()
#             cpu_parser = EnhancedCPUDataParser()
#             cpu_monitor = EnhancedCPUMonitor(cpu_provider, cpu_parser, update_interval=update_interval/2)
        
#         if show_network:
#             network_provider = EnhancedMacOSNetworkDataProvider()
#             network_parser = MacOSNetworkParser()
#             network_monitor = EnhancedNetworkMonitor(network_provider, network_parser, update_interval=update_interval/2)
        
#         # Create display manager
#         display_manager = SystemDisplayManager(
#             cpu_monitor=cpu_monitor,
#             network_monitor=network_monitor,
#             update_interval=update_interval,
#             detailed_view=detailed_view,
#             enable_alerts=enable_alerts,
#             show_cpu=show_cpu,
#             show_network=show_network
#         )
        
#         # Start display
#         display_manager.start()
        
#         # Wait for Ctrl+C
#         try:
#             while True:
#                 time.sleep(1)
#         except KeyboardInterrupt:
#             print("\nStopping system monitor...")
        
#         # Cleanup
#         display_manager.stop()
#         if cpu_monitor:
#             cpu_monitor.stop()
#         if network_monitor:
#             network_monitor.stop()
        
#     except Exception as e:
#         print(f"Error running system monitor: {e}")










"""
Command-line display for real-time system monitoring (CPU and Network).
"""
import os
import sys
import time
import signal
import threading
from typing import Dict, List, Any, Optional, Union, Callable

from system_metrics.providers.cpu_provider import EnhancedMacOSCPUDataProvider
from system_metrics.providers.network_provider import EnhancedMacOSNetworkDataProvider
from system_metrics.parsers.cpu_parser import EnhancedCPUDataParser
from system_metrics.parsers.network_parser import MacOSNetworkParser
from system_metrics.cpu import EnhancedCPUMonitor
from system_metrics.network import EnhancedNetworkMonitor
from system_metrics.alerts.thresholds import CPUThresholdMonitor
from system_metrics.alerts.network_thresholds import NetworkThresholdMonitor
from system_metrics.realtime.events import (
    MetricUpdateEvent, MetricEvent, Observer, MetricsEventDispatcher
)

from cli.formatting import (
    Colors, clear_screen, move_cursor, save_cursor_position, restore_cursor_position,
    format_overall_cpu, format_load_average, create_cpu_table, create_processes_table,
    get_terminal_size
)
from cli.network_formatting import (
    format_bandwidth, format_data_transferred, create_interfaces_table, 
    create_network_processes_table, create_connections_summary, create_wifi_summary,
    create_bandwidth_history_graph, format_live_bandwidth, format_active_connection_indicator
)


class SystemDisplayManager:
    """
    Manages the real-time display of system information in the terminal.
    
    This class displays CPU and/or network information based on configuration.
    """
    
    def __init__(self, 
                cpu_monitor: Optional[EnhancedCPUMonitor] = None,
                network_monitor: Optional[EnhancedNetworkMonitor] = None,
                update_interval: float = 1.0,
                detailed_view: bool = True,
                enable_alerts: bool = True,
                show_cpu: bool = True,
                show_network: bool = True):
        """
        Initialize the system display manager.
        
        Args:
            cpu_monitor: The CPU monitor instance (can be None if CPU monitoring is disabled)
            network_monitor: The network monitor instance (can be None if network monitoring is disabled)
            update_interval: How often to update the display (seconds)
            detailed_view: Whether to show detailed information
            enable_alerts: Whether to enable threshold alerts
            show_cpu: Whether to show CPU information
            show_network: Whether to show network information
        """
        self.cpu_monitor = cpu_monitor
        self.network_monitor = network_monitor
        self.update_interval = update_interval
        self.detailed_view = detailed_view
        self.enable_alerts = enable_alerts
        self.show_cpu = show_cpu and cpu_monitor is not None
        self.show_network = show_network and network_monitor is not None
        
        # Track history for metrics visualization
        self.cpu_history: List[float] = []
        self.rx_history: List[float] = []
        self.tx_history: List[float] = []
        self.max_history_points = 200  # Increased for better visualization
        
        # For tracking accumulated data during the session
        self.session_start_time = time.time()
        self.session_rx_bytes = 0
        self.session_tx_bytes = 0
        self.prev_total_rx = 0
        self.prev_total_tx = 0
        
        # Thread control
        self.running = False
        self.display_thread = None
        self.stop_event = threading.Event()
        
        # Initialize event dispatcher
        self.event_dispatcher = MetricsEventDispatcher()
        
        # Setup threshold monitors if enabled
        self.cpu_threshold_monitor = None
        self.network_threshold_monitor = None
        
        if self.enable_alerts:
            # Only create CPU threshold monitor if CPU monitoring is enabled
            if self.show_cpu and self.cpu_monitor:
                self.cpu_threshold_monitor = CPUThresholdMonitor(self.cpu_monitor)
                self.cpu_threshold_monitor.start()
            
            # Only create network threshold monitor if network monitoring is enabled
            if self.show_network and self.network_monitor:
                self.network_threshold_monitor = NetworkThresholdMonitor(self.network_monitor)
                self.network_threshold_monitor.start()
        
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
        
        # Start CPU monitor if it's active
        if self.show_cpu and self.cpu_monitor and hasattr(self.cpu_monitor, 'start') and not getattr(self.cpu_monitor, '_running', False):
            self.cpu_monitor.start()
            
        # Start network monitor if it's active
        if self.show_network and self.network_monitor and hasattr(self.network_monitor, 'start') and not getattr(self.network_monitor, '_running', False):
            self.network_monitor.start()
    
    def stop(self) -> None:
        """Stop the display loop and all monitors."""
        self.running = False
        self.stop_event.set()
        
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=self.update_interval + 1)
            self.display_thread = None
        
        # Stop threshold monitors if we started them
        if self.cpu_threshold_monitor:
            self.cpu_threshold_monitor.stop()
        
        if self.network_threshold_monitor:
            self.network_threshold_monitor.stop()
        
        # Stop event dispatcher
        if hasattr(self, 'event_dispatcher'):
            self.event_dispatcher.stop()
    
    def _display_loop(self) -> None:
        """Main display loop that updates the terminal."""
        try:
            # Hide cursor
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
            
            # Set a shorter update interval for more fluid display
            effective_interval = min(0.5, self.update_interval)
            
            while self.running and not self.stop_event.is_set():
                try:
                    # Clear screen
                    clear_screen()
                    
                    # Render the display
                    self._render_display()
                    
                    # Wait for next update
                    if self.stop_event.wait(effective_interval):
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
        """Render the complete system information display."""
        # Update alert ages
        if self.enable_alerts:
            self.update_alert_ages()
            
        try:
            # Determine rendering order based on configuration
            sections = []
            if self.show_cpu:
                sections.append(self._render_cpu_section)
            if self.show_network:
                sections.append(self._render_network_section)
            
            # Display header with timestamp
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            title = "macOS System Monitor"
            uptime_seconds = time.time() - self.session_start_time
            uptime_str = self._format_uptime(uptime_seconds)
            
            print(f"{Colors.BOLD}{title}{Colors.RESET}                              {Colors.DIM}{timestamp}{Colors.RESET}")
            print(f"Session uptime: {Colors.DIM}{uptime_str}{Colors.RESET}")
            print()
            
            # Display active alerts if any
            if self.active_alerts and self.enable_alerts:
                self._render_alerts()
                print()  # Empty line after alerts
            
            # Render each section
            for i, render_func in enumerate(sections):
                render_func()
                if i < len(sections) - 1:
                    print("\n" + "─" * 80 + "\n")  # Section divider
            
        except Exception as e:
            # Display error
            print(f"{Colors.FG_RED}Error rendering display: {e}{Colors.RESET}")
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in a human-readable way."""
        days, seconds = divmod(int(seconds), 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def _render_alerts(self) -> None:
        """Render active alerts."""
        if not self.active_alerts:
            return
            
        print(f"{Colors.BOLD}{Colors.FG_YELLOW}Active Alerts:{Colors.RESET}")
        
        for alert_id, alert in self.active_alerts.items():
            age_mins = alert['age'] / 60
            age_str = f"{age_mins:.1f} minutes ago"
            
            severity = alert['data'].get('severity', 'WARNING')
            if severity == 'CRITICAL':
                color = Colors.FG_RED
            else:
                color = Colors.FG_YELLOW
                
            print(f" {color}• {alert['message']}{Colors.RESET} ({Colors.DIM}{age_str}{Colors.RESET})")
    
    def _render_cpu_section(self) -> None:
        """Render the CPU information section."""
        try:
            if not self.cpu_monitor:
                print(f"{Colors.FG_YELLOW}CPU monitoring is not available.{Colors.RESET}")
                return
                
            # Get CPU data
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
                
            # Display CPU header with overall information
            print(f"{Colors.BOLD}CPU Information{Colors.RESET}")
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
            
            # Display CPU cores
            print(create_cpu_table(cores, show_detail=self.detailed_view))
            print()  # Empty line
            
            # Display top processes
            print(f"{Colors.BOLD}Top CPU Processes:{Colors.RESET}")
            print(create_processes_table(processes, max_processes=5))
            
        except Exception as e:
            print(f"{Colors.FG_RED}Error rendering CPU section: {e}{Colors.RESET}")
    
    def _render_network_section(self) -> None:
        """Render the network information section."""
        try:
            if not self.network_monitor:
                print(f"{Colors.FG_YELLOW}Network monitoring is not available.{Colors.RESET}")
                return
                
            # Get network data
            bandwidth_usage = self.network_monitor.get_bandwidth_usage()
            rx_bytes_per_sec = bandwidth_usage.get("rx_bytes_per_sec", 0)
            tx_bytes_per_sec = bandwidth_usage.get("tx_bytes_per_sec", 0)
            
            interfaces = self.network_monitor.get_interface_details()
            
            # Get connection statistics if available
            connection_stats = {}
            if hasattr(self.network_monitor, "get_connection_stats"):
                connection_stats = self.network_monitor.get_connection_stats()
            
            # Get WiFi details if available
            wifi_details = {}
            if hasattr(self.network_monitor, "get_wifi_details"):
                wifi_details = self.network_monitor.get_wifi_details()
            
            # Get top network processes if available
            network_processes = []
            if hasattr(self.network_monitor, "get_network_processes"):
                network_processes = self.network_monitor.get_network_processes()
            
            # Track bandwidth history
            self.rx_history.append(rx_bytes_per_sec)
            self.tx_history.append(tx_bytes_per_sec)
            if len(self.rx_history) > self.max_history_points:
                self.rx_history = self.rx_history[-self.max_history_points:]
                self.tx_history = self.tx_history[-self.max_history_points:]
            
            # Calculate session data usage
            total_rx = 0
            total_tx = 0
            
            # Sum up data from all interfaces
            for interface in interfaces:
                total_rx += interface.get("rx_bytes", 0)
                total_tx += interface.get("tx_bytes", 0)
            
            # Update session counters
            if self.prev_total_rx > 0:
                rx_diff = max(0, total_rx - self.prev_total_rx)
                self.session_rx_bytes += rx_diff
            if self.prev_total_tx > 0:
                tx_diff = max(0, total_tx - self.prev_total_tx)
                self.session_tx_bytes += tx_diff
                
            self.prev_total_rx = total_rx
            self.prev_total_tx = total_tx
            
            # Display network header
            print(f"{Colors.BOLD}Network Information{Colors.RESET}")
            print()
            
            # Display connection indicator
            if connection_stats:
                active_connections = connection_stats.get("established", 0)
                print(format_active_connection_indicator(active_connections))
                print()
            
            # Display real-time bandwidth with animation
            print(format_live_bandwidth(rx_bytes_per_sec, tx_bytes_per_sec, width=40))
            print()
            
            # Display bandwidth history graph
            term_width, _ = get_terminal_size()
            graph_width = min(term_width - 5, 80)  # Use available width but cap at 80
            print(create_bandwidth_history_graph(self.rx_history, self.tx_history, width=graph_width, height=5))
            print()
            
            # Display total data transferred
            print(format_data_transferred(total_rx, total_tx))
            print()
            
            # Display session data usage
            print(f"Session Traffic: {Colors.FG_CYAN}↓ {self._format_bytes(self.session_rx_bytes)}{Colors.RESET} | "
                  f"{Colors.FG_MAGENTA}↑ {self._format_bytes(self.session_tx_bytes)}{Colors.RESET}")
            print()
            
            # Display connection summary if available
            if connection_stats:
                print(create_connections_summary(connection_stats))
                print()
            
            # Display WiFi summary if connected
            if wifi_details and wifi_details.get("connected", False):
                wifi_summary = create_wifi_summary(wifi_details)
                if wifi_summary:
                    print(wifi_summary)
                    print()
            
            # Display network interfaces
            print(f"{Colors.BOLD}Active Network Interfaces:{Colors.RESET}")
            print(create_interfaces_table(interfaces, include_inactive=False))
            print()
            
            # Display top network processes if available
            if network_processes:
                print(f"{Colors.BOLD}Top Network Processes:{Colors.RESET}")
                print(create_network_processes_table(network_processes, max_processes=5))
            
        except Exception as e:
            print(f"{Colors.FG_RED}Error rendering network section: {e}{Colors.RESET}")
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format byte values with appropriate units."""
        if bytes_val >= 1_000_000_000:  # GB
            return f"{bytes_val/1_000_000_000:.2f} GB"
        elif bytes_val >= 1_000_000:  # MB
            return f"{bytes_val/1_000_000:.2f} MB"
        elif bytes_val >= 1_000:  # KB
            return f"{bytes_val/1_000:.2f} KB"
        else:  # B
            return f"{bytes_val} B"


def run_system_monitor(update_interval: float = 1.0,
                    detailed_view: bool = True,
                    enable_alerts: bool = True,
                    show_cpu: bool = True,
                    show_network: bool = True) -> None:
    """
    Run the system monitor with real-time CLI display.
    
    Args:
        update_interval: How often to update the display (seconds)
        detailed_view: Whether to show detailed information
        enable_alerts: Whether to enable threshold alerts
        show_cpu: Whether to show CPU information
        show_network: Whether to show network information
    """
    try:
        # Create the monitors only for the selected components
        cpu_monitor = None
        network_monitor = None
        
        if show_cpu:
            cpu_provider = EnhancedMacOSCPUDataProvider()
            cpu_parser = EnhancedCPUDataParser()
            cpu_monitor = EnhancedCPUMonitor(cpu_provider, cpu_parser, update_interval=update_interval/2)
        
        if show_network:
            network_provider = EnhancedMacOSNetworkDataProvider()
            network_parser = MacOSNetworkParser()
            # Update network monitor more frequently for more responsive display
            network_monitor = EnhancedNetworkMonitor(network_provider, network_parser, update_interval=min(0.5, update_interval/2))
        
        # Create display manager with a shorter update interval for smoother visuals
        display_manager = SystemDisplayManager(
            cpu_monitor=cpu_monitor,
            network_monitor=network_monitor,
            update_interval=min(0.5, update_interval),  # Cap at 0.5 seconds for fluid updates
            detailed_view=detailed_view,
            enable_alerts=enable_alerts,
            show_cpu=show_cpu,
            show_network=show_network
        )
        
        # Start display
        display_manager.start()
        
        # Wait for Ctrl+C
        try:
            while True:
                time.sleep(0.1)  # More responsive to keyboard interrupts
        except KeyboardInterrupt:
            print("\nStopping system monitor...")
        
        # Cleanup
        display_manager.stop()
        if cpu_monitor:
            cpu_monitor.stop()
        if network_monitor:
            network_monitor.stop()
        
    except Exception as e:
        print(f"Error running system monitor: {e}")