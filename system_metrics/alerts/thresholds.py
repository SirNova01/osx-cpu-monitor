"""
Threshold-based alerting system for CPU metrics.

This module provides functionality for generating alerts when CPU metrics
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


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


class AlertType(Enum):
    """Types of threshold alerts."""
    CPU_USAGE_HIGH = auto()
    CPU_USAGE_VERY_HIGH = auto()
    CPU_CORE_USAGE_HIGH = auto()
    CPU_USAGE_SUSTAINED = auto()
    CPU_TEMPERATURE_HIGH = auto()
    PROCESS_CPU_USAGE_HIGH = auto()
    
    
@dataclass
class ThresholdConfig:
    """Configuration for a threshold-based alert."""
    threshold: float
    duration_seconds: float  # How long the threshold must be exceeded
    severity: AlertSeverity
    alert_type: AlertType
    alert_message: str
    check_interval: float = 5.0
    cooldown_minutes: float = 10.0  # Time between repeated alerts


@dataclass
class AlertState:
    """State tracking for a threshold alert."""
    config: ThresholdConfig
    exceeded_since: Optional[float] = None
    last_alert_time: float = 0
    current_value: float = 0
    is_active: bool = False


class CPUThresholdMonitor:
    """
    Monitor for detecting when CPU metrics exceed thresholds for extended periods.
    
    This class tracks CPU metrics over time and generates alerts when configurable
    thresholds are exceeded for specified durations.
    """
    
    def __init__(self, cpu_monitor):
        """
        Initialize the threshold monitor.
        
        Args:
            cpu_monitor: The CPU monitor instance to use for metrics
        """
        self._cpu_monitor = cpu_monitor
        self._event_dispatcher = MetricsEventDispatcher()
        
        # Default thresholds configuration
        self._thresholds: Dict[str, ThresholdConfig] = {
            "cpu_usage_high": ThresholdConfig(
                threshold=80.0,
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.CPU_USAGE_HIGH,
                alert_message="CPU usage has been above {threshold}% for {duration} minutes"
            ),
            "cpu_usage_very_high": ThresholdConfig(
                threshold=90.0,
                duration_seconds=30.0,  # 30 seconds
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.CPU_USAGE_VERY_HIGH,
                alert_message="CPU usage is critically high at {value}%, exceeding {threshold}%"
            ),
            "cpu_usage_sustained": ThresholdConfig(
                threshold=70.0,
                duration_seconds=600.0,  # 10 minutes
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.CPU_USAGE_SUSTAINED,
                alert_message="CPU has been under sustained load (>{threshold}%) for {duration} minutes"
            ),
        }
        
        # Per-core thresholds - dynamically populated based on detected cores
        self._core_thresholds: Dict[int, Dict[str, ThresholdConfig]] = {}
        
        # Process thresholds
        self._process_thresholds: Dict[str, ThresholdConfig] = {
            "process_cpu_high": ThresholdConfig(
                threshold=50.0,
                duration_seconds=120.0,  # 2 minutes
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.PROCESS_CPU_USAGE_HIGH,
                alert_message="Process {process_name} (PID {pid}) has been using >{threshold}% CPU for {duration} minutes"
            )
        }
        
        # State tracking
        self._alert_states: Dict[str, AlertState] = {}
        self._core_alert_states: Dict[int, Dict[str, AlertState]] = {}
        self._process_alert_states: Dict[int, Dict[str, AlertState]] = {}
        
        # Tracking for sustained load analysis
        self._cpu_history: List[Tuple[float, float]] = []  # (timestamp, value)
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
            name="CPUThresholdMonitor"
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
            if name.startswith("cpu_"):
                alert_type = AlertType.CPU_USAGE_HIGH
            elif name.startswith("process_"):
                alert_type = AlertType.PROCESS_CPU_USAGE_HIGH
            else:
                alert_type = AlertType.CPU_USAGE_HIGH
                
            default_message = "Threshold {threshold}% exceeded for {duration} minutes"
            
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
        
        # Check CPU usage alerts
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
        
        # Check per-core alerts
        for core_id, core_states in self._core_alert_states.items():
            for name, state in core_states.items():
                if state.is_active:
                    result[f"core_{core_id}_{name}"] = {
                        "type": state.config.alert_type.name,
                        "severity": state.config.severity.name,
                        "threshold": state.config.threshold,
                        "current_value": state.current_value,
                        "core_id": core_id,
                        "duration": time.time() - (state.exceeded_since or time.time()),
                        "message": self._format_alert_message(state, core_id=core_id)
                    }
        
        # Check process alerts
        for pid, process_states in self._process_alert_states.items():
            for name, state in process_states.items():
                if state.is_active:
                    result[f"process_{pid}_{name}"] = {
                        "type": state.config.alert_type.name,
                        "severity": state.config.severity.name,
                        "threshold": state.config.threshold,
                        "current_value": state.current_value,
                        "pid": pid,
                        "duration": time.time() - (state.exceeded_since or time.time()),
                        "message": self._format_alert_message(state, pid=pid)
                    }
                    
        return result
    
    def _initialize_alert_states(self) -> None:
        """Initialize alert states for all thresholds."""
        # Initialize basic CPU alert states
        for name, config in self._thresholds.items():
            self._alert_states[name] = AlertState(config=config)
        
        # Initialize per-core alert states based on the current cores
        core_stats = self._get_core_stats()
        for core in core_stats:
            core_id = core.get("core_id")
            if core_id is not None:
                self._initialize_core_thresholds(core_id)
                
        # Process alert states are initialized dynamically as processes are detected
    
    def _initialize_core_thresholds(self, core_id: int) -> None:
        """Initialize thresholds for a CPU core."""
        if core_id in self._core_thresholds:
            return
            
        # Create threshold configs for this core
        self._core_thresholds[core_id] = {
            "core_usage_high": ThresholdConfig(
                threshold=90.0,
                duration_seconds=60.0,  # 1 minute
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.CPU_CORE_USAGE_HIGH,
                alert_message="Core {core_id} usage has been above {threshold}% for {duration} minutes"
            )
        }
        
        # Initialize alert states
        self._core_alert_states[core_id] = {
            name: AlertState(config=config)
            for name, config in self._core_thresholds[core_id].items()
        }
    
    def _check_loop(self) -> None:
        """Background thread that checks thresholds periodically."""
        check_interval = min(
            config.check_interval for config in self._thresholds.values()
        )
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Check CPU usage thresholds
                self._check_cpu_thresholds()
                
                # Check per-core thresholds
                self._check_core_thresholds()
                
                # Check process thresholds
                self._check_process_thresholds()
                
                # Check for sustained load patterns
                self._check_sustained_load()
                
            except Exception as e:
                print(f"Error checking thresholds: {e}")
            
            # Wait for next check interval or until shutdown
            if self._shutdown_event.wait(check_interval):
                break
    
    def _check_cpu_thresholds(self) -> None:
        """Check overall CPU usage against thresholds."""
        try:
            # Get current CPU usage
            if hasattr(self._cpu_monitor, "get_overall_cpu_breakdown"):
                cpu_data = self._cpu_monitor.get_overall_cpu_breakdown()
                cpu_usage = cpu_data.get("user", 0.0) + cpu_data.get("system", 0.0)
            else:
                # Fallback to simpler interface
                cpu_usage = self._cpu_monitor.get_cpu_percent()
                
            # Record in history for sustained load analysis
            current_time = time.time()
            self._cpu_history.append((current_time, cpu_usage))
            
            # Trim history to window
            cutoff_time = current_time - self._history_window
            self._cpu_history = [
                (ts, val) for ts, val in self._cpu_history
                if ts >= cutoff_time
            ]
                
            # Check each threshold
            for name, state in self._alert_states.items():
                # Skip non-CPU thresholds
                if not name.startswith("cpu_"):
                    continue
                    
                config = state.config
                state.current_value = cpu_usage
                
                # Check if threshold is exceeded
                if cpu_usage >= config.threshold:
                    # Start or continue tracking exceeded duration
                    if state.exceeded_since is None:
                        state.exceeded_since = current_time
                    
                    # Check if duration threshold is met
                    time_exceeded = current_time - state.exceeded_since
                    if time_exceeded >= config.duration_seconds and not state.is_active:
                        # Threshold has been exceeded for the required duration
                        # and an alert is not already active
                        
                        # Check cooldown period
                        if current_time - state.last_alert_time >= (config.cooldown_minutes * 60):
                            # Generate alert
                            self._generate_alert(state)
                            state.last_alert_time = current_time
                            state.is_active = True
                else:
                    # Reset tracking
                    state.exceeded_since = None
                    state.is_active = False
                    
        except Exception as e:
            print(f"Error checking CPU thresholds: {e}")
    
    def _check_core_thresholds(self) -> None:
        """Check per-core CPU usage against thresholds."""
        try:
            # Get current per-core stats
            core_stats = self._get_core_stats()
            if not core_stats:
                return
                
            current_time = time.time()
                
            # Ensure we have thresholds for all cores
            for core in core_stats:
                core_id = core.get("core_id")
                if core_id is not None and core_id not in self._core_thresholds:
                    self._initialize_core_thresholds(core_id)
            
            # Check each core against its thresholds
            for core in core_stats:
                core_id = core.get("core_id")
                if core_id is None or core_id not in self._core_alert_states:
                    continue
                    
                core_usage = core.get("usage", 0.0)
                
                # Check each threshold for this core
                for name, state in self._core_alert_states[core_id].items():
                    config = state.config
                    state.current_value = core_usage
                    
                    # Check if threshold is exceeded
                    if core_usage >= config.threshold:
                        # Start or continue tracking exceeded duration
                        if state.exceeded_since is None:
                            state.exceeded_since = current_time
                        
                        # Check if duration threshold is met
                        time_exceeded = current_time - state.exceeded_since
                        if time_exceeded >= config.duration_seconds and not state.is_active:
                            # Check cooldown period
                            if current_time - state.last_alert_time >= (config.cooldown_minutes * 60):
                                # Generate alert
                                self._generate_alert(state, core_id=core_id)
                                state.last_alert_time = current_time
                                state.is_active = True
                    else:
                        # Reset tracking
                        state.exceeded_since = None
                        state.is_active = False
                    
        except Exception as e:
            print(f"Error checking core thresholds: {e}")
    
    def _check_process_thresholds(self) -> None:
        """Check process CPU usage against thresholds."""
        try:
            # Get current process stats
            if not hasattr(self._cpu_monitor, "get_top_processes"):
                return
                
            processes = self._cpu_monitor.get_top_processes()
            if not processes:
                return
                
            current_time = time.time()
            
            # Track PIDs we've seen this round
            seen_pids = set()
            
            # Check each process against thresholds
            for proc in processes:
                pid = proc.get("pid")
                if pid is None:
                    continue
                    
                seen_pids.add(pid)
                cpu_percent = proc.get("cpu_percent", 0.0)
                command = proc.get("command", "unknown")
                
                # Initialize state tracking for this process if needed
                if pid not in self._process_alert_states:
                    self._process_alert_states[pid] = {}
                    for name, config in self._process_thresholds.items():
                        self._process_alert_states[pid][name] = AlertState(config=config)
                
                # Check each threshold for this process
                for name, state in self._process_alert_states[pid].items():
                    config = state.config
                    state.current_value = cpu_percent
                    
                    # Check if threshold is exceeded
                    if cpu_percent >= config.threshold:
                        # Start or continue tracking exceeded duration
                        if state.exceeded_since is None:
                            state.exceeded_since = current_time
                        
                        # Check if duration threshold is met
                        time_exceeded = current_time - state.exceeded_since
                        if time_exceeded >= config.duration_seconds and not state.is_active:
                            # Check cooldown period
                            if current_time - state.last_alert_time >= (config.cooldown_minutes * 60):
                                # Generate alert
                                self._generate_alert(state, pid=pid, process_name=command)
                                state.last_alert_time = current_time
                                state.is_active = True
                    else:
                        # Reset tracking
                        state.exceeded_since = None
                        state.is_active = False
            
            # Clean up states for processes that are no longer in the top list
            pids_to_remove = []
            for pid in self._process_alert_states:
                if pid not in seen_pids:
                    # Only remove if all alerts for this process are inactive
                    if not any(state.is_active for state in self._process_alert_states[pid].values()):
                        pids_to_remove.append(pid)
            
            for pid in pids_to_remove:
                del self._process_alert_states[pid]
                    
        except Exception as e:
            print(f"Error checking process thresholds: {e}")
    
    def _check_sustained_load(self) -> None:
        """
        Check for sustained CPU load patterns.
        
        This looks for patterns where the CPU has been under significant load
        for extended periods, even if it occasionally drops below thresholds.
        """
        try:
            # Need enough history for analysis
            if len(self._cpu_history) < 10:
                return
                
            # Check for sustained load threshold
            sustained_config = self._thresholds.get("cpu_usage_sustained")
            if not sustained_config:
                return
                
            sustained_state = self._alert_states.get("cpu_usage_sustained")
            if not sustained_state:
                return
                
            # Get average load over time windows
            current_time = time.time()
            
            # 5-minute average
            five_min_cutoff = current_time - 300
            five_min_data = [(ts, val) for ts, val in self._cpu_history if ts >= five_min_cutoff]
            if five_min_data:
                five_min_avg = sum(val for _, val in five_min_data) / len(five_min_data)
            else:
                five_min_avg = 0
            
            # 10-minute average (if we have enough history)
            ten_min_cutoff = current_time - 600
            ten_min_data = [(ts, val) for ts, val in self._cpu_history if ts >= ten_min_cutoff]
            if ten_min_data and len(ten_min_data) >= 10:  # Need at least 10 samples
                ten_min_avg = sum(val for _, val in ten_min_data) / len(ten_min_data)
            else:
                ten_min_avg = 0
                
            # Update current value to the longer average
            sustained_state.current_value = ten_min_avg if ten_min_avg > 0 else five_min_avg
            
            # Check if average load exceeds threshold
            if sustained_state.current_value >= sustained_config.threshold:
                # Start or continue tracking
                if sustained_state.exceeded_since is None:
                    sustained_state.exceeded_since = current_time
                
                # Check if duration requirement is met
                time_exceeded = current_time - sustained_state.exceeded_since
                if time_exceeded >= sustained_config.duration_seconds and not sustained_state.is_active:
                    # Check cooldown
                    if current_time - sustained_state.last_alert_time >= (sustained_config.cooldown_minutes * 60):
                        # Generate alert
                        self._generate_alert(sustained_state)
                        sustained_state.last_alert_time = current_time
                        sustained_state.is_active = True
            else:
                # Reset tracking
                sustained_state.exceeded_since = None
                sustained_state.is_active = False
                
        except Exception as e:
            print(f"Error checking sustained load: {e}")
    
    def _generate_alert(self, 
                       state: AlertState, 
                       core_id: Optional[int] = None,
                       pid: Optional[int] = None,
                       process_name: Optional[str] = None) -> None:
        """
        Generate an alert for a threshold violation.
        
        Args:
            state: The alert state
            core_id: Optional core ID for core-specific alerts
            pid: Optional process ID for process-specific alerts
            process_name: Optional process name for process alerts
        """
        # Format the alert message
        message = self._format_alert_message(state, core_id, pid, process_name)
        
        # Create the event data
        alert_data = {
            "threshold": state.config.threshold,
            "current_value": state.current_value,
            "duration_seconds": time.time() - (state.exceeded_since or time.time()),
            "alert_type": state.config.alert_type.name,
            "severity": state.config.severity.name
        }
        
        # Add core-specific data
        if core_id is not None:
            alert_data["core_id"] = core_id
            
        # Add process-specific data
        if pid is not None:
            alert_data["pid"] = pid
            alert_data["process_name"] = process_name or "unknown"
            
        # Publish the alert event
        self._event_dispatcher.publish_event(
            MetricEvent(
                event_type=MetricUpdateEvent.THRESHOLD_EXCEEDED,
                timestamp=time.time(),
                source="CPUThresholdMonitor",
                data=alert_data,
                message=message
            )
        )
        
        print(f"ALERT: {message}")  # Also print to console
    
    def _format_alert_message(self, 
                             state: AlertState, 
                             core_id: Optional[int] = None,
                             pid: Optional[int] = None,
                             process_name: Optional[str] = None) -> str:
        """
        Format an alert message with variable substitution.
        
        Args:
            state: The alert state
            core_id: Optional core ID for core-specific alerts
            pid: Optional process ID for process-specific alerts
            process_name: Optional process name for process alerts
            
        Returns:
            Formatted alert message
        """
        # Prepare variables for message formatting
        exceeded_duration = time.time() - (state.exceeded_since or time.time())
        minutes = round(exceeded_duration / 60, 1)
        
        format_vars = {
            "threshold": state.config.threshold,
            "value": round(state.current_value, 1),
            "duration": minutes,
            "core_id": core_id,
            "pid": pid,
            "process_name": process_name
        }
        
        # Format the message
        message = state.config.alert_message
        
        # Simple variable substitution
        for var_name, var_value in format_vars.items():
            if var_value is not None:
                message = message.replace(f"{{{var_name}}}", str(var_value))
                
        return message
    
    def _get_core_stats(self) -> List[Dict[str, Any]]:
        """Get the current per-core statistics."""
        if hasattr(self._cpu_monitor, "get_per_core_usage"):
            return self._cpu_monitor.get_per_core_usage()
        elif hasattr(self._cpu_monitor, "get_per_core_stats"):
            return self._cpu_monitor.get_per_core_stats()
        return []
