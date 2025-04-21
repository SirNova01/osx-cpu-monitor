"""
Disk metrics collection for macOS.
"""
import subprocess
from typing import Dict, List, Tuple, Optional

from .base import MetricsCollector, Metric


class DiskMetric:
    """Container for disk metrics relating to a specific mount point."""
    
    def __init__(self, device: str, mount_point: str):
        self.device = device
        self.mount_point = mount_point
        self.total = 0
        self.used = 0
        self.free = 0
        self.percent_used = 0.0
    
    def __str__(self) -> str:
        return (
            f"Device: {self.device}, "
            f"Mount: {self.mount_point}, "
            f"Total: {self.total} MB, "
            f"Used: {self.used} MB ({self.percent_used}%), "
            f"Free: {self.free} MB"
        )


class DiskMetricsCollector(MetricsCollector):
    """Collects disk usage metrics."""
    
    def __init__(self):
        super().__init__()
        # Dictionary to track metrics per mount point
        self._disk_metrics: Dict[str, DiskMetric] = {}
        
        # Initialize main metrics
        self._metrics = {
            "total_disk_space": Metric("total_disk_space", "Total disk space across all monitored file systems"),
            "used_disk_space": Metric("used_disk_space", "Used disk space across all monitored file systems"),
            "free_disk_space": Metric("free_disk_space", "Free disk space across all monitored file systems"),
        }
    
    def collect(self) -> Dict[str, Metric]:
        """Collect disk metrics."""
        try:
            # On macOS, we can use df command
            cmd = ["df", "-k"]  # -k for 1K blocks
            output = subprocess.check_output(cmd, text=True)
            
            # Parse disk usage from df output
            lines = output.splitlines()
            if len(lines) > 1:  # Skip header
                # Reset disk metrics
                self._disk_metrics = {}
                
                total_space = 0
                total_used = 0
                total_free = 0
                
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        device = parts[0]
                        blocks = int(parts[1])
                        used = int(parts[2])
                        available = int(parts[3])
                        capacity = parts[4].rstrip("%")
                        mount_point = parts[5]
                        
                        # Convert blocks to MB (1K blocks / 1024 = MB)
                        total_mb = blocks / 1024
                        used_mb = used / 1024
                        free_mb = available / 1024
                        percent = float(capacity)
                        
                        # Create a metric for this mount point
                        disk_metric = DiskMetric(device, mount_point)
                        disk_metric.total = total_mb
                        disk_metric.used = used_mb
                        disk_metric.free = free_mb
                        disk_metric.percent_used = percent
                        
                        # Store in our dictionary
                        self._disk_metrics[mount_point] = disk_metric
                        
                        # Create individual metrics for this mount point
                        mount_point_safe = mount_point.replace("/", "_")
                        self._metrics[f"disk_total_{mount_point_safe}"] = Metric(
                            f"disk_total_{mount_point_safe}", f"Total space at {mount_point}"
                        )
                        self._metrics[f"disk_used_{mount_point_safe}"] = Metric(
                            f"disk_used_{mount_point_safe}", f"Used space at {mount_point}"
                        )
                        self._metrics[f"disk_free_{mount_point_safe}"] = Metric(
                            f"disk_free_{mount_point_safe}", f"Free space at {mount_point}"
                        )
                        self._metrics[f"disk_percent_{mount_point_safe}"] = Metric(
                            f"disk_percent_{mount_point_safe}", f"Used percentage at {mount_point}"
                        )
                        
                        # Update the metrics
                        self._metrics[f"disk_total_{mount_point_safe}"].add_value(total_mb, "MB")
                        self._metrics[f"disk_used_{mount_point_safe}"].add_value(used_mb, "MB")
                        self._metrics[f"disk_free_{mount_point_safe}"].add_value(free_mb, "MB")
                        self._metrics[f"disk_percent_{mount_point_safe}"].add_value(percent, "%")
                        
                        # Accumulate totals (excluding special filesystems)
                        if not device.startswith("/dev/"):
                            continue
                        
                        total_space += total_mb
                        total_used += used_mb
                        total_free += free_mb
                
                # Update total metrics
                self._metrics["total_disk_space"].add_value(total_space, "MB")
                self._metrics["used_disk_space"].add_value(total_used, "MB")
                self._metrics["free_disk_space"].add_value(total_free, "MB")
            
        except Exception as e:
            # In case of error, log it and set default values
            print(f"Error collecting disk metrics: {e}")
            self._metrics["total_disk_space"].add_value(0, "MB")
            self._metrics["used_disk_space"].add_value(0, "MB")
            self._metrics["free_disk_space"].add_value(0, "MB")
        
        return self._metrics
    
    def get_disk_metrics(self) -> List[DiskMetric]:
        """Get metrics for all monitored disks."""
        return list(self._disk_metrics.values())
    
    def get_disk_metric(self, mount_point: str) -> Optional[DiskMetric]:
        """Get metrics for a specific mount point."""
        return self._disk_metrics.get(mount_point)
