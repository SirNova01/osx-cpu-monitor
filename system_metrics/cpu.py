
"""
Enhanced CPU monitoring service for macOS.

This module provides detailed CPU metrics including per-core usage breakdown
and user/system/idle percentages.
"""
import time
from threading import Thread, Lock
from typing import Dict, List, Optional, Tuple, Any

from system_metrics.base import Metric, MetricsCollector
from .providers.base import SystemDataProvider
from .parsers.base import DataParser


# Import our enhanced CPU provider and parser
# Note: In a real implementation, these would be properly imported from the actual package paths
# from .providers.enhanced_cpu_provider import EnhancedMacOSCPUDataProvider
# from .parsers.enhanced_cpu_parser import EnhancedCPUDataParser, EnhancedCPUStats, CoreStats

class EnhancedCPUMonitor:
    """
    Enhanced CPU monitor with detailed metrics and real-time updates.
    
    Features:
    - Overall CPU usage breakdown (user/system/idle)
    - Per-core CPU usage statistics
    - CPU frequency and temperature monitoring
    - Thermal pressure monitoring
    - Top CPU-consuming processes
    - Real-time updates with configurable intervals
    - Thread-safe access to metrics data
    """
    
    def __init__(self, provider: SystemDataProvider, parser: DataParser, update_interval: float = 5.0):
        """
        Initialize the CPU monitor.
        
        Args:
            provider: The system data provider to use
            parser: The parser for CPU data
            update_interval: Update interval in seconds (default: 5.0)
        """
        self._provider = provider
        self._parser = parser
        self._update_interval = update_interval
        
        # Initialize metrics storage
        self._metrics: Dict[str, Metric] = {
            # Overall CPU metrics
            "cpu_percent": Metric("cpu_percent", "Overall CPU usage percentage"),
            "user_percent": Metric("user_percent", "User CPU usage percentage"),
            "system_percent": Metric("system_percent", "System CPU usage percentage"),
            "idle_percent": Metric("idle_percent", "Idle CPU percentage"),
            
            # Load average metrics
            "load_avg_1min": Metric("load_avg_1min", "1-minute load average"),
            "load_avg_5min": Metric("load_avg_5min", "5-minute load average"),
            "load_avg_15min": Metric("load_avg_15min", "15-minute load average"),
            
            # Hardware metrics
            "cpu_count": Metric("cpu_count", "Number of CPU cores"),
            "physical_cores": Metric("physical_cores", "Number of physical CPU cores"),
            "logical_cores": Metric("logical_cores", "Number of logical CPU cores"),
            "cpu_freq_mhz": Metric("cpu_freq_mhz", "CPU frequency (MHz)"),
            
            # Thermal metrics (if available)
            "temperature": Metric("temperature", "CPU temperature (Celsius)"),
            "thermal_pressure": Metric("thermal_pressure", "Thermal pressure level"),
        }
        
        # Per-core metrics (will be populated during first update)
        self._core_metrics: Dict[str, Metric] = {}
        
        # Top processes metrics
        self._process_metrics: Dict[str, Metric] = {}
        
        # Concurrency control
        self._lock = Lock()
        self._running = False
        self._update_thread: Optional[Thread] = None
        self._latest_data: Optional[Any] = None
    
    def start(self) -> None:
        """Start the background updater thread."""
        if self._running:
            return
        
        self._running = True
        self._update_thread = Thread(target=self._updater_loop, daemon=True)
        self._update_thread.start()
    
    def stop(self) -> None:
        """Stop the background updater thread."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=self._update_interval + 1)
            self._update_thread = None
    
    def update_now(self) -> None:
        """Force an immediate update of CPU metrics."""
        self._update_metrics()
    
    def _updater_loop(self) -> None:
        """Background thread to update metrics at regular intervals."""
        while self._running:
            try:
                self._update_metrics()
            except Exception as e:
                print(f"Error updating CPU metrics: {e}")
            
            # Sleep for the update interval
            time.sleep(self._update_interval)
    
    def _update_metrics(self) -> None:
        """Update all CPU metrics."""
        try:
            # Get raw data from provider
            raw_data = self._provider.get_data()
            
            # Parse the data
            cpu_stats = self._parser.parse(raw_data)
            
            with self._lock:
                self._latest_data = cpu_stats
                
                # Update overall CPU metrics
                self._metrics["cpu_percent"].add_value(cpu_stats.cpu_percent, "%")
                self._metrics["user_percent"].add_value(cpu_stats.user_percent, "%")
                self._metrics["system_percent"].add_value(cpu_stats.system_percent, "%")
                self._metrics["idle_percent"].add_value(cpu_stats.idle_percent, "%")
                
                # Update load average metrics
                self._metrics["load_avg_1min"].add_value(cpu_stats.load_avg_1min)
                self._metrics["load_avg_5min"].add_value(cpu_stats.load_avg_5min)
                self._metrics["load_avg_15min"].add_value(cpu_stats.load_avg_15min)
                
                # Update hardware metrics
                self._metrics["cpu_count"].add_value(cpu_stats.cpu_count)
                self._metrics["physical_cores"].add_value(cpu_stats.physical_cores)
                self._metrics["logical_cores"].add_value(cpu_stats.logical_cores)
                self._metrics["cpu_freq_mhz"].add_value(cpu_stats.cpu_freq_mhz, "MHz")
                
                # Update thermal metrics if available
                if cpu_stats.temperature_celsius is not None:
                    self._metrics["temperature"].add_value(cpu_stats.temperature_celsius, "°C")
                self._metrics["thermal_pressure"].add_value(cpu_stats.thermal_pressure)
                
                # Update per-core metrics
                self._update_core_metrics(cpu_stats.core_stats)
                
                # Update process metrics
                self._update_process_metrics(cpu_stats.top_processes)
            
        except Exception as e:
            print(f"Error in _update_metrics: {e}")
    
    def _update_core_metrics(self, core_stats: List[Any]) -> None:
        """Update per-core CPU metrics."""
        for core in core_stats:
            core_id = core.core_id
            
            # Create core metrics if they don't exist
            core_prefix = f"core_{core_id}"
            if core_prefix not in self._core_metrics:
                self._core_metrics[f"{core_prefix}_usage"] = Metric(
                    f"{core_prefix}_usage", f"Core {core_id} usage percentage")
                self._core_metrics[f"{core_prefix}_user"] = Metric(
                    f"{core_prefix}_user", f"Core {core_id} user percentage")
                self._core_metrics[f"{core_prefix}_system"] = Metric(
                    f"{core_prefix}_system", f"Core {core_id} system percentage")
                self._core_metrics[f"{core_prefix}_idle"] = Metric(
                    f"{core_prefix}_idle", f"Core {core_id} idle percentage")
                self._core_metrics[f"{core_prefix}_freq"] = Metric(
                    f"{core_prefix}_freq", f"Core {core_id} frequency (MHz)")
            
            # Update core metrics
            self._core_metrics[f"{core_prefix}_usage"].add_value(core.usage_percent, "%")
            self._core_metrics[f"{core_prefix}_user"].add_value(core.user_percent, "%")
            self._core_metrics[f"{core_prefix}_system"].add_value(core.system_percent, "%")
            self._core_metrics[f"{core_prefix}_idle"].add_value(core.idle_percent, "%")
            
            if core.frequency_mhz > 0:
                self._core_metrics[f"{core_prefix}_freq"].add_value(core.frequency_mhz, "MHz")
    
    def _update_process_metrics(self, top_processes: List[Tuple[int, float, str]]) -> None:
        """Update top processes CPU metrics."""
        # Clear previous process metrics
        self._process_metrics = {}
        
        # Add new process metrics
        for idx, (pid, cpu_usage, command) in enumerate(top_processes[:10]):  # Limit to top 10
            metric_name = f"process_{idx}_cpu"
            self._process_metrics[metric_name] = Metric(
                metric_name, f"Process {pid} ({command}) CPU usage")
            self._process_metrics[metric_name].add_value(cpu_usage, "%")
    
    def get_metrics(self) -> Dict[str, Metric]:
        """Get all CPU metrics."""
        with self._lock:
            # Combine all metrics dictionaries
            all_metrics = {}
            all_metrics.update(self._metrics)
            all_metrics.update(self._core_metrics)
            all_metrics.update(self._process_metrics)
            return all_metrics
    
    def get_core_metrics(self) -> Dict[str, Metric]:
        """Get per-core CPU metrics."""
        with self._lock:
            return self._core_metrics.copy()
    
    def get_process_metrics(self) -> Dict[str, Metric]:
        """Get process CPU usage metrics."""
        with self._lock:
            return self._process_metrics.copy()
    
    def get_overall_cpu_breakdown(self) -> Dict[str, float]:
        """Get overall CPU usage breakdown."""
        with self._lock:
            return {
                "user": self._metrics["user_percent"].current_value.value if self._metrics["user_percent"].current_value else 0.0,
                "system": self._metrics["system_percent"].current_value.value if self._metrics["system_percent"].current_value else 0.0,
                "idle": self._metrics["idle_percent"].current_value.value if self._metrics["idle_percent"].current_value else 100.0,
            }
    
    def get_per_core_usage(self) -> List[Dict[str, Any]]:
        """Get per-core CPU usage statistics."""
        with self._lock:
            result = []
            core_count = self._metrics["cpu_count"].current_value.value if self._metrics["cpu_count"].current_value else 0
            
            for core_id in range(core_count):
                core_prefix = f"core_{core_id}"
                
                # Skip cores that don't have metrics yet
                if f"{core_prefix}_usage" not in self._core_metrics:
                    continue
                
                core_data = {
                    "core_id": core_id,
                    "usage": self._core_metrics[f"{core_prefix}_usage"].current_value.value 
                        if self._core_metrics[f"{core_prefix}_usage"].current_value else 0.0,
                    "user": self._core_metrics[f"{core_prefix}_user"].current_value.value 
                        if self._core_metrics[f"{core_prefix}_user"].current_value else 0.0,
                    "system": self._core_metrics[f"{core_prefix}_system"].current_value.value 
                        if self._core_metrics[f"{core_prefix}_system"].current_value else 0.0,
                    "idle": self._core_metrics[f"{core_prefix}_idle"].current_value.value 
                        if self._core_metrics[f"{core_prefix}_idle"].current_value else 100.0,
                }
                
                # Add frequency if available
                if f"{core_prefix}_freq" in self._core_metrics and self._core_metrics[f"{core_prefix}_freq"].current_value:
                    core_data["frequency_mhz"] = self._core_metrics[f"{core_prefix}_freq"].current_value.value
                
                result.append(core_data)
            
            return result
    
    def get_top_processes(self) -> List[Dict[str, Any]]:
        """Get top CPU-consuming processes."""
        with self._lock:
            if not self._latest_data:
                return []
            
            return [
                {"pid": pid, "cpu_percent": cpu_pct, "command": cmd}
                for pid, cpu_pct, cmd in self._latest_data.top_processes
            ]


class EnhancedCPUMetricsCollector(MetricsCollector):
    """
    CPU metrics collector compatible with the original metrics collection framework,
    but providing enhanced CPU monitoring capabilities.
    """
    
    def __init__(self, cpu_monitor: EnhancedCPUMonitor):
        """
        Initialize the enhanced CPU metrics collector.
        
        Args:
            cpu_monitor: An initialized EnhancedCPUMonitor instance
        """
        super().__init__()
        self._cpu_monitor = cpu_monitor
        
        # Initialize the CPU monitor if it's not already running
        if not self._cpu_monitor._running:
            self._cpu_monitor.start()
    
    def collect(self) -> Dict[str, Metric]:
        """Collect CPU metrics using the enhanced CPU monitor."""
        # Update CPU metrics
        self._cpu_monitor.update_now()
        
        # Get all metrics from the monitor
        all_metrics = self._cpu_monitor.get_metrics()
        
        # Update our metrics dictionary
        self._metrics = all_metrics
        
        return self._metrics
    
    def get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        metric = self._metrics.get("cpu_percent")
        if metric and metric.current_value:
            return metric.current_value.value
        return 0.0
    
    def get_load_average(self) -> List[float]:
        """Get current load average values."""
        result = []
        for period in ["load_avg_1min", "load_avg_5min", "load_avg_15min"]:
            metric = self._metrics.get(period)
            if metric and metric.current_value:
                result.append(metric.current_value.value)
            else:
                result.append(0.0)
        return result
    
    def get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        metric = self._metrics.get("cpu_count")
        if metric and metric.current_value:
            return metric.current_value.value
        return 0
    
    def get_cpu_breakdown(self) -> Dict[str, float]:
        """Get CPU usage breakdown between user, system, and idle."""
        return self._cpu_monitor.get_overall_cpu_breakdown()
    
    def get_per_core_stats(self) -> List[Dict[str, Any]]:
        """Get per-core CPU usage statistics."""
        return self._cpu_monitor.get_per_core_usage()
    
    def get_top_processes(self) -> List[Dict[str, Any]]:
        """Get top CPU-consuming processes."""
        return self._cpu_monitor.get_top_processes()


