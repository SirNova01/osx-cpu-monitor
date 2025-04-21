"""
Threshold-based alerting system for network metrics.

This module provides functionality for generating alerts when network metrics
exceed defined thresholds for specified durations.
""" 
import time
import threading
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass

from system_metrics.realtime.events import (
    MetricUpdateEvent, MetricEvent, MetricsEventDispatcher
)
from system_metrics.alerts.thresholds import (
    AlertSeverity, ThresholdConfig, AlertState
)


class NetworkAlertType(Enum):
    """Types of network threshold alerts."""
    BANDWIDTH_USAGE_HIGH = auto()
    BANDWIDTH_USAGE_VERY_HIGH = auto()
    DOWNLOAD_RATE_HIGH = auto()
    UPLOAD_RATE_HIGH = auto()
    TOTAL_BANDWIDTH_SUSTAINED = auto()
    CONNECTION_COUNT_HIGH = auto()
    INTERFACE_ERROR_RATE_HIGH = auto()
    PROCESS_BANDWIDTH_HIGH = auto()
    WIFI_SIGNAL_LOW = auto()


class NetworkThresholdMonitor:
    """
    Monitor for detecting when network metrics exceed thresholds for extended periods.
    
    This class tracks network metrics over time and generates alerts when configurable
    thresholds are exceeded for specified durations.
    """
    
    def __init__(self, network_monitor):
        """
        Initialize the network threshold monitor.
        
        Args:
            network_monitor: The network monitor instance to use for metrics
        """
        self._network_monitor = network_monitor
        self._event_dispatcher = MetricsEventDispatcher()
        
        # Default thresholds configuration
        self._thresholds: Dict[str, ThresholdConfig] = {
            "bandwidth_usage_high": ThresholdConfig(
                threshold=50_000_000,  # 50 MB/s
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.BANDWIDTH_USAGE_HIGH,
                alert_message="Network bandwidth usage has been above {threshold} bytes/s for {duration} minutes"
            ),
            "download_rate_high": ThresholdConfig(
                threshold=40_000_000,  # 40 MB/s
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.DOWNLOAD_RATE_HIGH,
                alert_message="Download bandwidth has been above {threshold} bytes/s for {duration} minutes"
            ),
            "upload_rate_high": ThresholdConfig(
                threshold=20_000_000,  # 20 MB/s
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.UPLOAD_RATE_HIGH,
                alert_message="Upload bandwidth has been above {threshold} bytes/s for {duration} minutes"
            ),
            "bandwidth_usage_very_high": ThresholdConfig(
                threshold=80_000_000,  # 80 MB/s
                duration_seconds=30.0,  # 30 seconds
                severity=AlertSeverity.CRITICAL,
                alert_type=NetworkAlertType.BANDWIDTH_USAGE_VERY_HIGH,
                alert_message="Network bandwidth usage is critically high at {value} bytes/s, exceeding {threshold} bytes/s"
            ),
            "bandwidth_usage_sustained": ThresholdConfig(
                threshold=10_000_000,  # 10 MB/s
                duration_seconds=600.0,  # 10 minutes
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.TOTAL_BANDWIDTH_SUSTAINED,
                alert_message="Network has been under sustained load (>{threshold} bytes/s) for {duration} minutes"
            ),
            "connection_count_high": ThresholdConfig(
                threshold=1000,  # 1000 connections
                duration_seconds=120.0,  # 2 minutes
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.CONNECTION_COUNT_HIGH,
                alert_message="Network connection count has been above {threshold} for {duration} minutes"
            ),
        }
        
        # Per-interface thresholds - dynamically populated based on detected interfaces
        self._interface_thresholds: Dict[str, Dict[str, ThresholdConfig]] = {}
        
        # Process thresholds
        self._process_thresholds: Dict[str, ThresholdConfig] = {
            "process_bandwidth_high": ThresholdConfig(
                threshold=10_000_000,  # 10 MB/s
                duration_seconds=120.0,  # 2 minutes
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.PROCESS_BANDWIDTH_HIGH,
                alert_message="Process {process_name} has been using >{threshold} bytes/s bandwidth for {duration} minutes"
            )
        }
        
        # WiFi thresholds
        self._wifi_thresholds: Dict[str, ThresholdConfig] = {
            "wifi_signal_low": ThresholdConfig(
                threshold=-75,  # RSSI threshold in dBm
                duration_seconds=300.0,  # 5 minutes
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.WIFI_SIGNAL_LOW,
                alert_message="WiFi signal strength has been below {threshold} dBm for {duration} minutes"
            )
        }
        
        # State tracking
        self._alert_states: Dict[str, AlertState] = {}
        self._interface_alert_states: Dict[str, Dict[str, AlertState]] = {}
        self._process_alert_states: Dict[str, Dict[str, AlertState]] = {}
        self._wifi_alert_states: Dict[str, AlertState] = {}
        
        # Tracking for sustained bandwidth analysis
        self._bandwidth_history: List[Tuple[float, float]] = []  # (timestamp, value)
        self._history_window = 3600  # seconds = 1 hour
        
        # Thread control
        self._running = False
        self._check_thread = None
        self._shutdown_event = threading.Event()
    
    def start(self) -> None:
        """Start the threshold monitoring."""
        if self._running:
            return
        
        # Initialize alert states
        self._initialize_alert_states()
        
        # Start the monitoring thread
        self._running = True
        self._shutdown_event.clear()
        self._check_thread = threading.Thread(
            target=self._check_loop,
            daemon=True,
            name="NetworkThresholdMonitor"
        )
        self._check_thread.start()
    
    def stop(self) -> None:
        """Stop the threshold monitoring."""
        self._running = False
        self._shutdown_event.set()
        
        if self._check_thread and self._check_thread.is_alive():
            self._check_thread.join(timeout=5.0)
            self._check_thread = None
    
    def set_threshold(self, 
                      name: str,
                      threshold: float,
                      duration_seconds: float,
                      severity: AlertSeverity = AlertSeverity.WARNING,
                      alert_message: Optional[str] = None) -> None:
        """
        Set or update a threshold configuration.
        
        Args:
            name: Name of the threshold
            threshold: Threshold value
            duration_seconds: How long the threshold must be exceeded
            severity: Alert severity level
            alert_message: Optional custom alert message
        """
        if name not in self._thresholds:
            # Create a new threshold config
            alert_type = None
            if name.startswith("bandwidth_"):
                alert_type = NetworkAlertType.BANDWIDTH_USAGE_HIGH
            elif name.startswith("download_"):
                alert_type = NetworkAlertType.DOWNLOAD_RATE_HIGH
            elif name.startswith("upload_"):
                alert_type = NetworkAlertType.UPLOAD_RATE_HIGH
            elif name.startswith("connection_"):
                alert_type = NetworkAlertType.CONNECTION_COUNT_HIGH
            elif name.startswith("process_"):
                alert_type = NetworkAlertType.PROCESS_BANDWIDTH_HIGH
            elif name.startswith("wifi_"):
                alert_type = NetworkAlertType.WIFI_SIGNAL_LOW
            else:
                alert_type = NetworkAlertType.BANDWIDTH_USAGE_HIGH
                
            default_message = "Network threshold {threshold} exceeded for {duration} minutes"
            
            self._thresholds[name] = ThresholdConfig(
                threshold=threshold,
                duration_seconds=duration_seconds,
                severity=severity,
                alert_type=alert_type,
                alert_message=alert_message or default_message
            )
        else:
            # Update existing threshold
            config = self._thresholds[name]
            config.threshold = threshold
            config.duration_seconds = duration_seconds
            config.severity = severity
            if alert_message:
                config.alert_message = alert_message
                
        # Reset state for this threshold
        if name in self._alert_states:
            self._alert_states[name] = AlertState(config=self._thresholds[name])
    
    def get_active_alerts(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently active alerts.
        
        Returns:
            Dictionary of active alerts
        """
        result = {}
        
        # Check bandwidth and other general network alerts
        for name, state in self._alert_states.items():
            if state.is_active:
                result[name] = {
                    "type": state.config.alert_type.name,
                    "severity": state.config.severity.name,
                    "threshold": state.config.threshold,
                    "current_value": state.current_value,
                    "duration": time.time() - (state.exceeded_since or time.time()),
                    "message": self._format_alert_message(state)
                }
        
        # Check per-interface alerts
        for interface_name, interface_states in self._interface_alert_states.items():
            for name, state in interface_states.items():
                if state.is_active:
                    result[f"interface_{interface_name}_{name}"] = {
                        "type": state.config.alert_type.name,
                        "severity": state.config.severity.name,
                        "threshold": state.config.threshold,
                        "current_value": state.current_value,
                        "interface_name": interface_name,
                        "duration": time.time() - (state.exceeded_since or time.time()),
                        "message": self._format_alert_message(state, interface_name=interface_name)
                    }
        
        # Check process alerts
        for process_name, process_states in self._process_alert_states.items():
            for name, state in process_states.items():
                if state.is_active:
                    result[f"process_{process_name}_{name}"] = {
                        "type": state.config.alert_type.name,
                        "severity": state.config.severity.name,
                        "threshold": state.config.threshold,
                        "current_value": state.current_value,
                        "process_name": process_name,
                        "duration": time.time() - (state.exceeded_since or time.time()),
                        "message": self._format_alert_message(state, process_name=process_name)
                    }
        
        # Check WiFi alerts
        for name, state in self._wifi_alert_states.items():
            if state.is_active:
                result[name] = {
                    "type": state.config.alert_type.name,
                    "severity": state.config.severity.name,
                    "threshold": state.config.threshold,
                    "current_value": state.current_value,
                    "duration": time.time() - (state.exceeded_since or time.time()),
                    "message": self._format_alert_message(state)
                }
                    
        return result
    
    def _initialize_alert_states(self) -> None:
        """Initialize alert states for all thresholds."""
        # Initialize basic network alert states
        for name, config in self._thresholds.items():
            self._alert_states[name] = AlertState(config=config)
        
        # Initialize per-interface alert states based on the current interfaces
        interface_details = self._get_interface_details()
        for interface in interface_details:
            name = interface.get("name")
            if name:
                self._initialize_interface_thresholds(name)
                
        # Initialize WiFi alert states
        for name, config in self._wifi_thresholds.items():
            self._wifi_alert_states[name] = AlertState(config=config)
                
        # Process alert states are initialized dynamically as processes are detected
    
    def _initialize_interface_thresholds(self, interface_name: str) -> None:
        """Initialize thresholds for a network interface."""
        if interface_name in self._interface_thresholds:
            return
            
        # Create threshold configs for this interface
        self._interface_thresholds[interface_name] = {
            "interface_bandwidth_high": ThresholdConfig(
                threshold=40_000_000,  # 40 MB/s
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.BANDWIDTH_USAGE_HIGH,
                alert_message="Interface {interface_name} usage has been above {threshold} bytes/s for {duration} minutes"
            ),
            "interface_error_rate_high": ThresholdConfig(
                threshold=100,  # 100 errors
                duration_seconds=300.0,  # 5 minutes
                severity=AlertSeverity.WARNING,
                alert_type=NetworkAlertType.INTERFACE_ERROR_RATE_HIGH,
                alert_message="Interface {interface_name} has had more than {threshold} errors in the last {duration} minutes"
            )
        }
        
        # Initialize alert states
        self._interface_alert_states[interface_name] = {
            name: AlertState(config=config)
            for name, config in self._interface_thresholds[interface_name].items()
        }
    
    def _check_loop(self) -> None:
        """Background thread that checks thresholds periodically."""
        check_interval = min(
            config.check_interval for config in self._thresholds.values()
        )
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Check bandwidth usage thresholds
                self._check_bandwidth_thresholds()
                
                # Check per-interface thresholds
                self._check_interface_thresholds()
                
                # Check process thresholds
                self._check_process_thresholds()
                
                # Check WiFi thresholds
                self._check_wifi_thresholds()
                
                # Check for sustained bandwidth patterns
                self._check_sustained_bandwidth()
                
                # Check connection count thresholds
                self._check_connection_thresholds()
                
            except Exception as e:
                print(f"Error checking network thresholds: {e}")
            
            # Wait for next check interval or until shutdown
            if self._shutdown_event.wait(check_interval):
                break
    
    def _check_bandwidth_thresholds(self) -> None:
        """Check overall bandwidth usage against thresholds."""
        try:
            # Get current bandwidth usage
            bandwidth_usage = self._network_monitor.get_bandwidth_usage()
            rx_bytes_per_sec = bandwidth_usage.get("rx_bytes_per_sec", 0)
            tx_bytes_per_sec = bandwidth_usage.get("tx_bytes_per_sec", 0)
            total_bandwidth = rx_bytes_per_sec + tx_bytes_per_sec
            
            # Record in history for sustained bandwidth analysis
            current_time = time.time()
            self._bandwidth_history.append((current_time, total_bandwidth))
            
            # Trim history to window
            cutoff_time = current_time - self._history_window
            self._bandwidth_history = [
                (ts, val) for ts, val in self._bandwidth_history
                if ts >= cutoff_time
            ]
                
            # Check total bandwidth threshold
            self._check_threshold("bandwidth_usage_high", total_bandwidth, current_time)
            self._check_threshold("bandwidth_usage_very_high", total_bandwidth, current_time)
            
            # Check download threshold
            self._check_threshold("download_rate_high", rx_bytes_per_sec, current_time)
            
            # Check upload threshold
            self._check_threshold("upload_rate_high", tx_bytes_per_sec, current_time)
                    
        except Exception as e:
            print(f"Error checking bandwidth thresholds: {e}")
    
    def _check_threshold(self, name: str, current_value: float, timestamp: float) -> None:
        """
        Check if a specific metric exceeds its threshold.
        
        Args:
            name: The name of the threshold to check
            current_value: The current value of the metric
            timestamp: The current timestamp
        """
        # Skip if this threshold doesn't exist
        if name not in self._alert_states:
            return
            
        state = self._alert_states[name]
        config = state.config
        state.current_value = current_value
        
        # Check if threshold is exceeded
        threshold_exceeded = False
        if name == "wifi_signal_low":
            # For WiFi signal, lower values are worse
            threshold_exceeded = current_value <= config.threshold
        else:
            # For most other metrics, higher values are worse
            threshold_exceeded = current_value >= config.threshold
            
        if threshold_exceeded:
            # Start or continue tracking exceeded duration
            if state.exceeded_since is None:
                state.exceeded_since = timestamp
            
            # Check if duration threshold is met
            time_exceeded = timestamp - state.exceeded_since
            if time_exceeded >= config.duration_seconds and not state.is_active:
                # Threshold has been exceeded for the required duration
                # and an alert is not already active
                
                # Check cooldown period
                if timestamp - state.last_alert_time >= (config.cooldown_minutes * 60):
                    # Generate alert
                    self._generate_alert(state)
                    state.last_alert_time = timestamp
                    state.is_active = True
        else:
            # Reset tracking
            state.exceeded_since = None
            state.is_active = False
    
    def _check_interface_thresholds(self) -> None:
        """Check per-interface network usage against thresholds."""
        try:
            # Get current interface details
            interface_details = self._get_interface_details()
            if not interface_details:
                return
                
            current_time = time.time()
                
            # Ensure we have thresholds for all interfaces
            for interface in interface_details:
                name = interface.get("name")
                if name and name not in self._interface_thresholds:
                    self._initialize_interface_thresholds(name)
            
            # Check each interface against its thresholds
            for interface in interface_details:
                name = interface.get("name")
                if not name or name not in self._interface_alert_states:
                    continue
                
                # Skip inactive interfaces
                if interface.get("status", "").lower() != "active":
                    continue
                    
                # Calculate bandwidth based on rx_bytes and tx_bytes
                # Note: This depends on how the interface details are collected and tracked
                rx_bytes = interface.get("rx_bytes", 0)
                tx_bytes = interface.get("tx_bytes", 0)
                total_bytes = rx_bytes + tx_bytes
                
                # For bandwidth, we'd need to calculate the rate over time
                # If the monitor provides bandwidth per interface, use that instead
                interface_bandwidth = 0
                if hasattr(self._network_monitor, "get_interface_bandwidth"):
                    interface_bandwidth = self._network_monitor.get_interface_bandwidth(name)
                
                # Check bandwidth threshold
                if "interface_bandwidth_high" in self._interface_alert_states[name]:
                    bandwidth_state = self._interface_alert_states[name]["interface_bandwidth_high"]
                    bandwidth_config = bandwidth_state.config
                    bandwidth_state.current_value = interface_bandwidth
                    
                    if interface_bandwidth >= bandwidth_config.threshold:
                        if bandwidth_state.exceeded_since is None:
                            bandwidth_state.exceeded_since = current_time
                        
                        time_exceeded = current_time - bandwidth_state.exceeded_since
                        if time_exceeded >= bandwidth_config.duration_seconds and not bandwidth_state.is_active:
                            if current_time - bandwidth_state.last_alert_time >= (bandwidth_config.cooldown_minutes * 60):
                                self._generate_alert(bandwidth_state, interface_name=name)
                                bandwidth_state.last_alert_time = current_time
                                bandwidth_state.is_active = True
                    else:
                        bandwidth_state.exceeded_since = None
                        bandwidth_state.is_active = False
                
                # Check error rate threshold
                error_count = interface.get("errors", 0)
                if "interface_error_rate_high" in self._interface_alert_states[name]:
                    error_state = self._interface_alert_states[name]["interface_error_rate_high"]
                    error_config = error_state.config
                    error_state.current_value = error_count
                    
                    if error_count >= error_config.threshold:
                        if error_state.exceeded_since is None:
                            error_state.exceeded_since = current_time
                        
                        time_exceeded = current_time - error_state.exceeded_since
                        if time_exceeded >= error_config.duration_seconds and not error_state.is_active:
                            if current_time - error_state.last_alert_time >= (error_config.cooldown_minutes * 60):
                                self._generate_alert(error_state, interface_name=name)
                                error_state.last_alert_time = current_time
                                error_state.is_active = True
                    else:
                        error_state.exceeded_since = None
                        error_state.is_active = False
                    
        except Exception as e:
            print(f"Error checking interface thresholds: {e}")
    
    def _check_process_thresholds(self) -> None:
        """Check process network usage against thresholds."""
        try:
            # Check if the monitor provides process network usage data
            if not hasattr(self._network_monitor, "get_network_processes"):
                return
                
            processes = self._network_monitor.get_network_processes()
            if not processes:
                return
                
            current_time = time.time()
            
            # Track process names we've seen this round
            seen_processes = set()
            
            # Check each process against thresholds
            for proc in processes:
                process_name = proc.get("name", "unknown")
                seen_processes.add(process_name)
                bandwidth = proc.get("bandwidth", 0.0)
                
                # Initialize state tracking for this process if needed
                if process_name not in self._process_alert_states:
                    self._process_alert_states[process_name] = {}
                    for name, config in self._process_thresholds.items():
                        self._process_alert_states[process_name][name] = AlertState(config=config)
                
                # Check bandwidth threshold for this process
                if "process_bandwidth_high" in self._process_alert_states[process_name]:
                    state = self._process_alert_states[process_name]["process_bandwidth_high"]
                    config = state.config
                    state.current_value = bandwidth
                    
                    if bandwidth >= config.threshold:
                        if state.exceeded_since is None:
                            state.exceeded_since = current_time
                        
                        time_exceeded = current_time - state.exceeded_since
                        if time_exceeded >= config.duration_seconds and not state.is_active:
                            if current_time - state.last_alert_time >= (config.cooldown_minutes * 60):
                                self._generate_alert(state, process_name=process_name)
                                state.last_alert_time = current_time
                                state.is_active = True
                    else:
                        state.exceeded_since = None
                        state.is_active = False
            
            # Clean up states for processes that are no longer in the list
            processes_to_remove = []
            for process_name in self._process_alert_states:
                if process_name not in seen_processes:
                    # Only remove if all alerts for this process are inactive
                    if not any(state.is_active for state in self._process_alert_states[process_name].values()):
                        processes_to_remove.append(process_name)
            
            for process_name in processes_to_remove:
                del self._process_alert_states[process_name]
                    
        except Exception as e:
            print(f"Error checking process thresholds: {e}")
    
    def _check_wifi_thresholds(self) -> None:
        """Check WiFi metrics against thresholds."""
        try:
            # Get current WiFi information
            if not hasattr(self._network_monitor, "get_wifi_details"):
                return
                
            wifi_info = self._network_monitor.get_wifi_details()
            if not wifi_info or not wifi_info.get("connected", False):
                return
                
            current_time = time.time()
            
            # Check signal strength threshold
            signal_strength = wifi_info.get("signal_strength", 0)
            self._check_threshold("wifi_signal_low", signal_strength, current_time)
                
        except Exception as e:
            print(f"Error checking WiFi thresholds: {e}")
    
    def _check_connection_thresholds(self) -> None:
        """Check connection count thresholds."""
        try:
            # Get current connection statistics
            if not hasattr(self._network_monitor, "get_connection_stats"):
                return
                
            connection_stats = self._network_monitor.get_connection_stats()
            total_connections = connection_stats.get("total", 0)
            
            current_time = time.time()
            
            # Check threshold
            self._check_threshold("connection_count_high", total_connections, current_time)
                
        except Exception as e:
            print(f"Error checking connection thresholds: {e}")
    
    def _check_sustained_bandwidth(self) -> None:
        """
        Check for sustained bandwidth patterns.
        
        This looks for patterns where the network has been under significant load
        for extended periods, even if it occasionally drops below thresholds.
        """
        try:
            # Need enough history for analysis
            if len(self._bandwidth_history) < 10:
                return
                
            # Check for sustained bandwidth threshold
            sustained_config = self._thresholds.get("bandwidth_usage_sustained")
            if not sustained_config:
                return
                
            sustained_state = self._alert_states.get("bandwidth_usage_sustained")
            if not sustained_state:
                return
                
            # Get average bandwidth over time windows
            current_time = time.time()
            
            # 5-minute average
            five_min_cutoff = current_time - 300
            five_min_data = [(ts, val) for ts, val in self._bandwidth_history if ts >= five_min_cutoff]
            if five_min_data:
                five_min_avg = sum(val for _, val in five_min_data) / len(five_min_data)
            else:
                five_min_avg = 0
            
            # 10-minute average (if we have enough history)
            ten_min_cutoff = current_time - 600
            ten_min_data = [(ts, val) for ts, val in self._bandwidth_history if ts >= ten_min_cutoff]
            if ten_min_data and len(ten_min_data) >= 10:  # Need at least 10 samples
                ten_min_avg = sum(val for _, val in ten_min_data) / len(ten_min_data)
            else:
                ten_min_avg = 0
                
            # Update current value to the longer average
            sustained_state.current_value = ten_min_avg if ten_min_avg > 0 else five_min_avg
            
            # Check if threshold is exceeded
            self._check_threshold("bandwidth_usage_sustained", sustained_state.current_value, current_time)
                
        except Exception as e:
            print(f"Error checking sustained bandwidth: {e}")
    
    def _generate_alert(self, 
                       state: AlertState, 
                       interface_name: Optional[str] = None,
                       process_name: Optional[str] = None) -> None:
        """
        Generate an alert for a threshold violation.
        
        Args:
            state: The alert state
            interface_name: Optional interface name for interface-specific alerts
            process_name: Optional process name for process-specific alerts
        """
        # Format the alert message
        message = self._format_alert_message(state, interface_name, process_name)
        
        # Create the event data
        alert_data = {
            "threshold": state.config.threshold,
            "current_value": state.current_value,
            "duration_seconds": time.time() - (state.exceeded_since or time.time()),
            "alert_type": state.config.alert_type.name,
            "severity": state.config.severity.name
        }
        
        # Add interface-specific data
        if interface_name is not None:
            alert_data["interface_name"] = interface_name
            
        # Add process-specific data
        if process_name is not None:
            alert_data["process_name"] = process_name
            
        # Publish the alert event
        self._event_dispatcher.publish_event(
            MetricEvent(
                event_type=MetricUpdateEvent.THRESHOLD_EXCEEDED,
                timestamp=time.time(),
                source="NetworkThresholdMonitor",
                data=alert_data,
                message=message
            )
        )
        
        print(f"NETWORK ALERT: {message}")  # Also print to console
    
    def _format_alert_message(self, 
                             state: AlertState, 
                             interface_name: Optional[str] = None,
                             process_name: Optional[str] = None) -> str:
        """
        Format an alert message with variable substitution.
        
        Args:
            state: The alert state
            interface_name: Optional interface name for interface-specific alerts
            process_name: Optional process name for process-specific alerts
            
        Returns:
            Formatted alert message
        """
        # Prepare variables for message formatting
        exceeded_duration = time.time() - (state.exceeded_since or time.time())
        minutes = round(exceeded_duration / 60, 1)
        
        format_vars = {
            "threshold": self._format_value_with_unit(state.config.threshold),
            "value": self._format_value_with_unit(state.current_value),
            "duration": minutes,
            "interface_name": interface_name,
            "process_name": process_name
        }
        
        # Format the message
        message = state.config.alert_message
        
        # Simple variable substitution
        for var_name, var_value in format_vars.items():
            if var_value is not None:
                message = message.replace(f"{{{var_name}}}", str(var_value))
                
        return message
    
    def _format_value_with_unit(self, value: float) -> str:
        """
        Format a numeric value with appropriate units based on context.
        
        Args:
            value: The numeric value
            
        Returns:
            Formatted string with units
        """
        # For large bandwidth values (bytes/sec), use more readable units
        if value > 1_000_000:  # > 1 MB/s
            return f"{value/1_000_000:.2f} MB/s"
        elif value > 1_000:  # > 1 KB/s
            return f"{value/1_000:.2f} KB/s"
            
        # Otherwise return the raw value
        return str(value)
    
    def _get_interface_details(self) -> List[Dict[str, Any]]:
        """Get detailed information for all network interfaces."""
        if hasattr(self._network_monitor, "get_interface_details"):
            return self._network_monitor.get_interface_details()
        return []
