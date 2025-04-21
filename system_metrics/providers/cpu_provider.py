"""
Enhanced CPU data provider for macOS.
"""
import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from system_metrics.providers.base import CommandExecutionProvider


class EnhancedMacOSCPUDataProvider(CommandExecutionProvider):
    """Provides detailed CPU data on macOS including per-core metrics."""
    
    def is_available(self) -> bool:
        """Check if this provider can be used on the current system."""
        return os.uname().sysname == "Darwin"
    
    def get_data(self) -> Dict[str, Any]:
        """Get detailed CPU data from the system."""
        result = {}
        
        try:
            # Get overall CPU usage using top
            top_output = self.execute_command("top -l 2 -n 0 -s 1")
            # Only use the second sample for more accurate readings
            sections = top_output.split("Processes:")
            if len(sections) > 2:
                result["top_output"] = sections[2]
            else:
                result["top_output"] = sections[-1]
            
            # Get detailed per-core CPU usage using powermetrics
            # Note: This requires sudo on most systems, so we make it optional
            try:
                # Sample for a brief period to get per-core statistics
                powermetrics_cmd = "powermetrics --samplers cpu_power -n 1 -i 1000"
                try:
                    powermetrics_output = self.execute_command(powermetrics_cmd)
                    result["powermetrics_output"] = powermetrics_output
                except RuntimeError as e:
                    # Fallback to another approach if powermetrics fails (often due to permissions)
                    result["powermetrics_error"] = str(e)
            except Exception as e:
                result["powermetrics_error"] = str(e)
            
            # Get per-core information using sysctl
            sysctl_output = self.execute_command("sysctl -a | grep machdep.cpu")
            result["sysctl_cpu_output"] = sysctl_output
            
            # Get CPU temperature and thermal pressure if available (Big Sur+)
            try:
                thermal_output = self.execute_command("pmset -g therm")
                result["thermal_output"] = thermal_output
            except RuntimeError:
                # Not available or requires different approach
                pass
                
            # Get CPU topology details
            try:
                topology_cmd = "sysctl hw.physicalcpu hw.logicalcpu hw.packages hw.tbfrequency hw.cpufrequency"
                topology_output = self.execute_command(topology_cmd)
                result["cpu_topology"] = topology_output
            except RuntimeError:
                pass
                
            # Get load average
            loadavg_output = self.execute_command("sysctl -n vm.loadavg")
            result["loadavg_output"] = loadavg_output
            
            # Get process CPU usage breakdown (top processes)
            process_cmd = "ps -Ao pid,pcpu,pmem,comm -r | head -11"  # Header + top 10
            process_output = self.execute_command(process_cmd)
            result["top_processes"] = process_output
            
            # Attempt to get per-core cpu usage with vm_stat
            try:
                # iostat can provide some per-CPU data on macOS
                iostat_cmd = "iostat -c 2"  # Show CPU stats with 2 samples
                iostat_output = self.execute_command(iostat_cmd)
                result["iostat_output"] = iostat_output
            except RuntimeError:
                pass
            
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def get_per_core_data(self) -> Dict[str, Any]:
        """
        Get per-core CPU data using a separate method for targeted collection.
        
        Returns a dictionary with per-core CPU usage data.
        """
        result = {}
        
        try:
            # Use sysctl to get the number of cores
            cpu_count_output = self.execute_command("sysctl -n hw.ncpu")
            core_count = int(cpu_count_output.strip())
            result["core_count"] = core_count
            
            # Use powermetrics if available for detailed per-core stats
            try:
                output = self.execute_command("powermetrics --samplers cpu_power -n 1 -i 500")
                result["per_core_data"] = output
            except RuntimeError:
                # Fallback for per-core data if powermetrics is unavailable
                # This might vary by macOS version
                try:
                    top_output = self.execute_command("top -l 1 -n 0 -stats pid,command,cpu")
                    result["top_per_core"] = top_output
                except RuntimeError:
                    pass
            
        except Exception as e:
            result["error"] = str(e)
            
        return result