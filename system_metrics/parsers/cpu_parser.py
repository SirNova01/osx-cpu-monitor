"""
Enhanced parser for detailed CPU data.
"""
import re
from dataclasses import dataclass
from typing import Dict, Any, List, NamedTuple, Optional, Tuple

from system_metrics.parsers.base import DataParser
# from system_metrics.parsers.cpu_parser import CPUStats


@dataclass
class CoreStats:
    """Statistics for an individual CPU core."""
    core_id: int
    usage_percent: float
    user_percent: float
    system_percent: float
    idle_percent: float
    frequency_mhz: float = 0.0
    temperature_celsius: Optional[float] = None

class EnhancedCPUStats(NamedTuple):
    # Non-default (required) fields first
    cpu_percent: float
    user_percent: float
    system_percent: float
    idle_percent: float
    load_avg_1min: float
    load_avg_5min: float
    load_avg_15min: float
    cpu_count: int
    physical_cores: int
    logical_cores: int

    # Fields with default values come afterward
    nice_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    temperature_celsius: Optional[float] = None
    thermal_pressure: str = "NOMINAL"
    core_stats: List[CoreStats] = []
    top_processes: List[Tuple[int, float, str]] = []


class EnhancedCPUDataParser(DataParser[EnhancedCPUStats]):
    """Parser for enhanced CPU data with detailed breakdowns."""
    
    def parse(self, raw_data: Dict[str, Any]) -> EnhancedCPUStats:
        """Parse raw CPU data into a structured enhanced format."""
        # Parse basic CPU usage
        cpu_percent, user_percent, system_percent, idle_percent, nice_percent = self._parse_cpu_usage(raw_data)
        
        # Parse load averages
        load_avg_1min, load_avg_5min, load_avg_15min = self._parse_load_average(raw_data)
        
        # Parse CPU topology
        cpu_count, physical_cores, logical_cores, cpu_freq_mhz = self._parse_cpu_topology(raw_data)
        
        # Parse thermal information if available
        temperature, thermal_pressure = self._parse_thermal_info(raw_data)
        
        # Parse per-core statistics
        core_stats = self._parse_per_core_stats(raw_data, cpu_count)
        
        # Parse top processes by CPU usage
        top_processes = self._parse_top_processes(raw_data)
        
        return EnhancedCPUStats(
            cpu_percent=cpu_percent,
            user_percent=user_percent,
            system_percent=system_percent,
            idle_percent=idle_percent,
            nice_percent=nice_percent,
            load_avg_1min=load_avg_1min,
            load_avg_5min=load_avg_5min,
            load_avg_15min=load_avg_15min,
            cpu_count=cpu_count,
            physical_cores=physical_cores,
            logical_cores=logical_cores,
            cpu_freq_mhz=cpu_freq_mhz,
            temperature_celsius=temperature,
            thermal_pressure=thermal_pressure,
            core_stats=core_stats,
            top_processes=top_processes
        )
    
    def _parse_cpu_usage(self, raw_data: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
        """Parse overall CPU usage percentages."""
        cpu_percent = 0.0
        user_percent = 0.0
        system_percent = 0.0
        idle_percent = 100.0
        nice_percent = 0.0
        
        if "top_output" in raw_data:
            # Parse macOS top output
            for line in raw_data["top_output"].splitlines():
                if "CPU usage" in line:
                    # Example: "CPU usage: 10.34% user, 15.67% sys, 73.99% idle"
                    user_match = re.search(r"(\d+\.\d+)% user", line)
                    sys_match = re.search(r"(\d+\.\d+)% sys", line)
                    idle_match = re.search(r"(\d+\.\d+)% idle", line)
                    
                    if user_match:
                        user_percent = float(user_match.group(1))
                    if sys_match:
                        system_percent = float(sys_match.group(1))
                    if idle_match:
                        idle_percent = float(idle_match.group(1))
                    
                    cpu_percent = user_percent + system_percent
                    break
        
        return cpu_percent, user_percent, system_percent, idle_percent, nice_percent
    
    def _parse_load_average(self, raw_data: Dict[str, Any]) -> Tuple[float, float, float]:
        """Parse load average values."""
        load_avg_1min = 0.0
        load_avg_5min = 0.0
        load_avg_15min = 0.0
        
        if "loadavg_output" in raw_data:
            # Format on macOS: "{ 1.23 2.34 3.45 }"
            load_match = re.findall(r"(\d+\.\d+)", raw_data["loadavg_output"])
            if len(load_match) >= 3:
                load_avg_1min = float(load_match[0])
                load_avg_5min = float(load_match[1])
                load_avg_15min = float(load_match[2])
        
        return load_avg_1min, load_avg_5min, load_avg_15min
    
    def _parse_cpu_topology(self, raw_data: Dict[str, Any]) -> Tuple[int, int, int, float]:
        """Parse CPU topology information."""
        cpu_count = 0
        physical_cores = 0
        logical_cores = 0
        cpu_freq_mhz = 0.0
        
        # Parse CPU topology from sysctl output
        if "cpu_topology" in raw_data:
            # Extract physical and logical cores
            physical_match = re.search(r"hw.physicalcpu: (\d+)", raw_data["cpu_topology"])
            logical_match = re.search(r"hw.logicalcpu: (\d+)", raw_data["cpu_topology"])
            freq_match = re.search(r"hw.cpufrequency: (\d+)", raw_data["cpu_topology"])
            
            if physical_match:
                physical_cores = int(physical_match.group(1))
            if logical_match:
                logical_cores = int(logical_match.group(1))
            if freq_match:
                # Convert Hz to MHz
                cpu_freq_mhz = int(freq_match.group(1)) / 1_000_000
                
            # Use logical cores as the total CPU count
            cpu_count = logical_cores if logical_cores > 0 else physical_cores
        
        return cpu_count, physical_cores, logical_cores, cpu_freq_mhz
    
    def _parse_thermal_info(self, raw_data: Dict[str, Any]) -> Tuple[Optional[float], str]:
        """Parse thermal information if available."""
        temperature = None
        thermal_pressure = "NOMINAL"
        
        if "thermal_output" in raw_data:
            # Try to extract thermal pressure - macOS Big Sur+
            pressure_match = re.search(r"CPU Power: (\w+)", raw_data["thermal_output"])
            if pressure_match:
                thermal_pressure = pressure_match.group(1)
            
            # Some macOS versions report thermal levels in the output
            # This is a simplified approach - real implementation would be more robust
            temp_match = re.search(r"CPU die temperature: (\d+\.\d+)", raw_data.get("powermetrics_output", ""))
            if temp_match:
                temperature = float(temp_match.group(1))
        
        return temperature, thermal_pressure
    
    def _parse_per_core_stats(self, raw_data: Dict[str, Any], cpu_count: int) -> List[CoreStats]:
        """Parse per-core CPU statistics."""
        core_stats = []
        
        # Only attempt to parse per-core data if we have the number of cores
        if cpu_count <= 0:
            return core_stats
        
        # First try to parse from powermetrics if available, which has the most detailed per-core info
        if "powermetrics_output" in raw_data and "powermetrics_error" not in raw_data:
            # Extract per-core usage from powermetrics output
            # Powermetrics format varies by macOS version
            core_data = raw_data["powermetrics_output"]
            
            # Sample parsing for Big Sur/Monterey output format
            core_sections = re.findall(r"CPU (\d+) .*?(\d+\.\d+)%\s+user.*?(\d+\.\d+)%\s+system.*?(\d+\.\d+)%\s+idle", 
                                      core_data, re.DOTALL)
            
            for match in core_sections:
                if len(match) >= 4:
                    core_id = int(match[0])
                    user_pct = float(match[1])
                    system_pct = float(match[2])
                    idle_pct = float(match[3])
                    
                    # Extract frequency if available
                    freq_mhz = 0.0
                    freq_match = re.search(rf"CPU {core_id}.*?(\d+)\s+MHz", core_data)
                    if freq_match:
                        freq_mhz = float(freq_match.group(1))
                    
                    core_stats.append(CoreStats(
                        core_id=core_id,
                        usage_percent=user_pct + system_pct,
                        user_percent=user_pct,
                        system_percent=system_pct,
                        idle_percent=idle_pct,
                        frequency_mhz=freq_mhz
                    ))
        
        # If powermetrics didn't provide per-core stats, use a fallback approach
        if not core_stats and "iostat_output" in raw_data:
            # Try to extract per-core info from iostat output
            # IoStat doesn't provide as much detail, but it's more accessible
            lines = raw_data["iostat_output"].splitlines()
            cpu_lines = [line for line in lines if re.match(r"^\s+cpu\d+\s+", line)]
            
            for line in cpu_lines:
                # Try to parse core ID and usage
                match = re.match(r"^\s+cpu(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", line)
                if match:
                    core_id = int(match.group(1))
                    user_pct = float(match.group(2))
                    system_pct = float(match.group(3))
                    idle_pct = float(match.group(4))
                    
                    core_stats.append(CoreStats(
                        core_id=core_id,
                        usage_percent=user_pct + system_pct,
                        user_percent=user_pct,
                        system_percent=system_pct,
                        idle_percent=idle_pct
                    ))
        
        # If we still don't have per-core stats, create placeholder entries
        if not core_stats:
            # Create equal distribution as a fallback
            overall_cpu = raw_data.get("cpu_percent", 0.0)
            overall_user = raw_data.get("user_percent", 0.0)
            overall_system = raw_data.get("system_percent", 0.0)
            overall_idle = raw_data.get("idle_percent", 100.0)
            
            for core_id in range(cpu_count):
                core_stats.append(CoreStats(
                    core_id=core_id,
                    usage_percent=overall_cpu / cpu_count if cpu_count > 0 else 0,
                    user_percent=overall_user / cpu_count if cpu_count > 0 else 0,
                    system_percent=overall_system / cpu_count if cpu_count > 0 else 0,
                    idle_percent=overall_idle
                ))
        
        return core_stats
    
    def _parse_top_processes(self, raw_data: Dict[str, Any]) -> List[Tuple[int, float, str]]:
        """Parse information about top CPU-using processes."""
        top_processes = []
        
        if "top_processes" in raw_data:
            # Parse the output of ps command
            lines = raw_data["top_processes"].splitlines()[1:]  # Skip header
            
            for line in lines:
                parts = line.split(None, 3)
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        cpu_usage = float(parts[1])
                        command = parts[3] if len(parts) > 3 else "Unknown"
                        
                        top_processes.append((pid, cpu_usage, command))
                    except (ValueError, IndexError):
                        continue
        
        return top_processes
