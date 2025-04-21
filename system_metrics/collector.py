"""
Main module for collecting all system metrics.
"""
from typing import Dict, List, Optional, Any

from system_metrics.cpu import EnhancedCPUMetricsCollector

from .base import MetricsCollector, Metric, SystemMetricsCollector
# from .cpu import CPUMetricsCollector
from .memory import MemoryMetricsCollector
from .disk import DiskMetricsCollector


class MacOSSystemMetricsCollector:
    """
    Main class for collecting and retrieving all system metrics on macOS.
    
    This class combines the functionality of different metric collectors
    and provides a unified interface for accessing system metrics.
    """
    
    def __init__(self):
        self._system_collector = SystemMetricsCollector()
        
        # Initialize and register individual collectors
        self._cpu_collector = EnhancedCPUMetricsCollector()
        self._memory_collector = MemoryMetricsCollector()
        self._disk_collector = DiskMetricsCollector()
        
        self._system_collector.register_collector(self._cpu_collector)
        self._system_collector.register_collector(self._memory_collector)
        self._system_collector.register_collector(self._disk_collector)
    
    def collect_metrics(self) -> Dict[str, Dict[str, Metric]]:
        """
        Collect all system metrics.
        
        Returns:
            A dictionary containing all collected metrics, organized by collector.
        """
        return self._system_collector.collect_all()
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """
        Get a specific metric by name.
        
        Args:
            name: The name of the metric to retrieve.
            
        Returns:
            The requested Metric object, or None if not found.
        """
        metrics = self._system_collector.get_all_metrics()
        return metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        """
        Get all collected metrics.
        
        Returns:
            A dictionary mapping metric names to Metric objects.
        """
        return self._system_collector.get_all_metrics()
    
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """
        Get a summary of CPU metrics.
        
        Returns:
            A dictionary containing CPU usage information.
        """
        return {
            "cpu_percent": self._cpu_collector.get_cpu_percent(),
            "load_average": self._cpu_collector.get_load_average(),
            "cpu_count": self._cpu_collector.get_cpu_count()
        }
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """
        Get a summary of memory metrics.
        
        Returns:
            A dictionary containing memory usage information.
        """
        total, used, free, percent = self._memory_collector.get_memory_usage()
        return {
            "total_mb": total,
            "used_mb": used,
            "free_mb": free,
            "percent_used": percent
        }
    
    def get_disk_metrics(self) -> Dict[str, Any]:
        """
        Get a summary of disk metrics.
        
        Returns:
            A dictionary containing disk usage information.
        """
        disk_metrics = self._disk_collector.get_disk_metrics()
        return {
            "filesystems": [
                {
                    "device": disk.device,
                    "mount_point": disk.mount_point,
                    "total_mb": disk.total,
                    "used_mb": disk.used,
                    "free_mb": disk.free,
                    "percent_used": disk.percent_used
                }
                for disk in disk_metrics
            ],
            "total_mb": self._get_metric_value("total_disk_space"),
            "used_mb": self._get_metric_value("used_disk_space"),
            "free_mb": self._get_metric_value("free_disk_space"),
        }
    
    def _get_metric_value(self, name: str) -> Any:
        """Helper method to get a metric's current value."""
        metric = self.get_metric(name)
        if metric and metric.current_value:
            return metric.current_value.value
        return 0
    
    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a complete summary of all system metrics.
        
        Returns:
            A dictionary containing summary information for all metric types.
        """
        # Make sure we have the latest metrics
        self.collect_metrics()
        
        return {
            "cpu": self.get_cpu_metrics(),
            "memory": self.get_memory_metrics(),
            "disk": self.get_disk_metrics(),
        }
