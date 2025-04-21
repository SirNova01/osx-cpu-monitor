"""
Memory metrics collection for macOS.
"""
import subprocess
from typing import Dict, Optional, Tuple

from .base import MetricsCollector, Metric


class MemoryMetricsCollector(MetricsCollector):
    """Collects memory usage metrics."""
    
    def __init__(self):
        super().__init__()
        # Initialize metrics
        self._metrics = {
            "total_memory": Metric("total_memory", "Total physical memory"),
            "used_memory": Metric("used_memory", "Used physical memory"),
            "free_memory": Metric("free_memory", "Free physical memory"),
            "used_percent": Metric("used_percent", "Percentage of memory used"),
            "swap_total": Metric("swap_total", "Total swap memory"),
            "swap_used": Metric("swap_used", "Used swap memory"),
            "swap_free": Metric("swap_free", "Free swap memory"),
            "swap_percent": Metric("swap_percent", "Percentage of swap used"),
        }
    
    def collect(self) -> Dict[str, Metric]:
        """Collect memory metrics."""
        # Collect physical memory metrics
        self._collect_physical_memory()
        
        # Collect swap memory metrics
        self._collect_swap_memory()
        
        # Return updated metrics
        return self._metrics
    
    def _collect_physical_memory(self) -> None:
        """Collect physical memory usage."""
        try:
            # On macOS, we can use vm_stat to get memory usage
            cmd = ["vm_stat"]
            output = subprocess.check_output(cmd, text=True)
            
            # Parse memory info from vm_stat output
            page_size = 4096  # Default page size in bytes
            free_pages = 0
            active_pages = 0
            inactive_pages = 0
            wired_pages = 0
            
            for line in output.splitlines():
                if "page size of" in line:
                    # Extract page size, e.g., "Mach Virtual Memory Statistics: (page size of 4096 bytes)"
                    parts = line.split()
                    if len(parts) >= 8:
                        try:
                            page_size = int(parts[7])
                        except ValueError:
                            pass
                elif "Pages free:" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            free_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
                elif "Pages active:" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            active_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
                elif "Pages inactive:" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            inactive_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
                elif "Pages wired down:" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            wired_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
            
            # Calculate memory values in bytes
            used_pages = active_pages + inactive_pages + wired_pages
            total_pages = used_pages + free_pages
            
            total_memory = total_pages * page_size
            used_memory = used_pages * page_size
            free_memory = free_pages * page_size
            
            # Convert to MB for better readability
            total_memory_mb = total_memory / (1024 * 1024)
            used_memory_mb = used_memory / (1024 * 1024)
            free_memory_mb = free_memory / (1024 * 1024)
            
            # Calculate percentage
            used_percent = (used_memory / total_memory) * 100 if total_memory > 0 else 0
            
            # Update metrics
            self._metrics["total_memory"].add_value(total_memory_mb, "MB")
            self._metrics["used_memory"].add_value(used_memory_mb, "MB")
            self._metrics["free_memory"].add_value(free_memory_mb, "MB")
            self._metrics["used_percent"].add_value(used_percent, "%")
            
        except Exception as e:
            # In case of error, log it and set default values
            print(f"Error collecting physical memory: {e}")
            self._metrics["total_memory"].add_value(0, "MB")
            self._metrics["used_memory"].add_value(0, "MB")
            self._metrics["free_memory"].add_value(0, "MB")
            self._metrics["used_percent"].add_value(0, "%")
    
    def _collect_swap_memory(self) -> None:
        """Collect swap memory usage."""
        try:
            # On macOS, we can use sysctl to get swap info
            cmd_total = ["sysctl", "-n", "vm.swapusage"]
            output = subprocess.check_output(cmd_total, text=True).strip()
            
            # Example output: "total = 1024.00M used = 714.75M free = 309.25M (encrypted)"
            parts = output.split()
            
            swap_total_mb = 0
            swap_used_mb = 0
            swap_free_mb = 0
            
            if len(parts) >= 6:
                try:
                    swap_total_mb = float(parts[2].rstrip("M"))
                    swap_used_mb = float(parts[5].rstrip("M"))
                    swap_free_mb = float(parts[8].rstrip("M"))
                except (ValueError, IndexError):
                    pass
            
            # Calculate percentage
            swap_percent = (swap_used_mb / swap_total_mb) * 100 if swap_total_mb > 0 else 0
            
            # Update metrics
            self._metrics["swap_total"].add_value(swap_total_mb, "MB")
            self._metrics["swap_used"].add_value(swap_used_mb, "MB")
            self._metrics["swap_free"].add_value(swap_free_mb, "MB")
            self._metrics["swap_percent"].add_value(swap_percent, "%")
            
        except Exception as e:
            # In case of error, log it and set default values
            print(f"Error collecting swap memory: {e}")
            self._metrics["swap_total"].add_value(0, "MB")
            self._metrics["swap_used"].add_value(0, "MB")
            self._metrics["swap_free"].add_value(0, "MB")
            self._metrics["swap_percent"].add_value(0, "%")
    
    def get_memory_usage(self) -> Tuple[float, float, float, float]:
        """
        Get current memory usage.
        
        Returns:
            Tuple containing (total_mb, used_mb, free_mb, used_percent)
        """
        total = self._metrics["total_memory"].current_value.value if self._metrics["total_memory"].current_value else 0
        used = self._metrics["used_memory"].current_value.value if self._metrics["used_memory"].current_value else 0
        free = self._metrics["free_memory"].current_value.value if self._metrics["free_memory"].current_value else 0
        percent = self._metrics["used_percent"].current_value.value if self._metrics["used_percent"].current_value else 0
        
        return (total, used, free, percent)
