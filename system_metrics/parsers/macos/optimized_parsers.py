"""
Optimized parsers for macOS-specific providers.
"""
import re
from typing import Dict, Any, List, Tuple, Optional, NamedTuple

from ..base import DataParser
from ..cpu_parser import CPUStats
from ..memory_parser import MemoryStats
from ..disk_parser import DiskStats, FilesystemInfo


class OptimizedCPUDataParser(DataParser[CPUStats]):
    """Parser for data from the optimized macOS CPU provider."""
    
    def parse(self, raw_data: Dict[str, Any]) -> CPUStats:
        """Parse raw CPU data into a structured format."""
        # Default values
        cpu_percent = 0.0
        load_avg_1min = 0.0
        load_avg_5min = 0.0
        load_avg_15min = 0.0
        cpu_count = 0
        cpu_freq_mhz = 0.0
        
        # Check for error
        if "error" in raw_data:
            return CPUStats(
                cpu_percent, load_avg_1min, load_avg_5min, 
                load_avg_15min, cpu_count, cpu_freq_mhz
            )
        
        # Use pre-parsed data if available (most efficient)
        if "parsed_cpu" in raw_data and "total_percent" in raw_data["parsed_cpu"]:
            cpu_percent = raw_data["parsed_cpu"]["total_percent"]
        elif "top_output" in raw_data:
            # Fall back to parsing top output
            cpu_percent = self._parse_top_output(raw_data["top_output"])
            
        # Get load average from pre-parsed data
        if "parsed_loadavg" in raw_data:
            load_avg_1min = raw_data["parsed_loadavg"].get("1min", 0.0)
            load_avg_5min = raw_data["parsed_loadavg"].get("5min", 0.0)
            load_avg_15min = raw_data["parsed_loadavg"].get("15min", 0.0)
        elif "loadavg_output" in raw_data:
            # Fall back to parsing loadavg output
            load_avg_1min, load_avg_5min, load_avg_15min = self._parse_load_average(raw_data["loadavg_output"])
            
        # Get CPU count
        if "cpu_count" in raw_data:
            cpu_count = raw_data["cpu_count"]
            
        # Get CPU frequency
        if "cpu_freq_mhz" in raw_data:
            cpu_freq_mhz = raw_data["cpu_freq_mhz"]
            
        return CPUStats(
            cpu_percent, load_avg_1min, load_avg_5min, 
            load_avg_15min, cpu_count, cpu_freq_mhz
        )
    
    def _parse_top_output(self, top_output: str) -> float:
        """Parse CPU usage from top output."""
        try:
            # Parse the output format: "CPU usage: 9.15% user, 15.23% sys, 75.60% idle"
            match = re.search(r"CPU usage: ([\d\.]+)% user, ([\d\.]+)% sys", top_output)
            if match:
                user_pct = float(match.group(1))
                sys_pct = float(match.group(2))
                return user_pct + sys_pct
        except (ValueError, AttributeError):
            pass
            
        return 0.0
    
    def _parse_load_average(self, loadavg_output: str) -> Tuple[float, float, float]:
        """Parse load average from sysctl output."""
        try:
            # Format: "{ 1.23 2.34 3.45 }"
            matches = re.findall(r"[\d\.]+", loadavg_output)
            if len(matches) >= 3:
                return float(matches[0]), float(matches[1]), float(matches[2])
        except (ValueError, IndexError):
            pass
            
        return 0.0, 0.0, 0.0


class OptimizedMemoryDataParser(DataParser[MemoryStats]):
    """Parser for data from the optimized macOS memory provider."""
    
    def parse(self, raw_data: Dict[str, Any]) -> MemoryStats:
        """Parse raw memory data into a structured format."""
        # Default values
        total_memory_mb = 0.0
        used_memory_mb = 0.0
        free_memory_mb = 0.0
        used_percent = 0.0
        swap_total_mb = 0.0
        swap_used_mb = 0.0
        swap_free_mb = 0.0
        swap_percent = 0.0
        
        # Check for error
        if "error" in raw_data:
            return MemoryStats(
                total_memory_mb, used_memory_mb, free_memory_mb, used_percent,
                swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
            )
        
        # Get physical memory information
        if "parsed_memory" in raw_data:
            # Use pre-parsed values
            mem = raw_data["parsed_memory"]
            bytes_to_mb = lambda b: b / (1024 * 1024)
            
            # If we have total_memory_bytes, use that for total
            if "total_memory_bytes" in raw_data:
                total_memory_mb = bytes_to_mb(raw_data["total_memory_bytes"])
            else:
                # Otherwise use the computed total
                total_memory_mb = bytes_to_mb(mem.get("total_computed_bytes", 0))
                
            used_memory_mb = bytes_to_mb(mem.get("used_bytes", 0))
            free_memory_mb = bytes_to_mb(mem.get("free_bytes", 0))
            used_percent = mem.get("percent_used", 0.0)
            
        elif "vm_stat_output" in raw_data:
            # Fall back to parsing vm_stat output
            if "total_memory_bytes" in raw_data:
                # Use the total from sysctl if available
                total_bytes = raw_data["total_memory_bytes"]
                total_memory_mb, used_memory_mb, free_memory_mb, used_percent = self._parse_vm_stat(
                    raw_data["vm_stat_output"], 
                    total_bytes
                )
            else:
                # Otherwise calculate from vm_stat
                total_memory_mb, used_memory_mb, free_memory_mb, used_percent = self._parse_vm_stat(
                    raw_data["vm_stat_output"]
                )
        
        # Get swap information
        if "parsed_swap" in raw_data:
            # Use pre-parsed values
            swap = raw_data["parsed_swap"]
            bytes_to_mb = lambda b: b / (1024 * 1024)
            
            swap_total_mb = bytes_to_mb(swap.get("total_bytes", 0))
            swap_used_mb = bytes_to_mb(swap.get("used_bytes", 0))
            swap_free_mb = bytes_to_mb(swap.get("free_bytes", 0))
            swap_percent = swap.get("percent_used", 0.0)
            
        elif "swap_output" in raw_data:
            # Fall back to parsing swap output
            swap_total_mb, swap_used_mb, swap_free_mb, swap_percent = self._parse_swap(
                raw_data["swap_output"]
            )
            
        return MemoryStats(
            total_memory_mb, used_memory_mb, free_memory_mb, used_percent,
            swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
        )
    
    def _parse_vm_stat(self, vm_stat_output: str, total_bytes: int = 0) -> Tuple[float, float, float, float]:
        """Parse memory stats from vm_stat output."""
        # Default page size
        page_size = 4096
        
        # Extract page size if available
        match = re.search(r"page size of (\d+) bytes", vm_stat_output)
        if match:
            page_size = int(match.group(1))
            
        # Parse memory pages
        pages = {}
        for line in vm_stat_output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                try:
                    # Extract the number, ignore any trailing dots or text
                    match = re.search(r"(\d+)", value.strip())
                    if match:
                        pages[key] = int(match.group(1))
                except (ValueError, AttributeError):
                    pass
        
        # Calculate memory values
        free_pages = pages.get("pages_free", 0) + pages.get("pages_inactive", 0)
        used_pages = pages.get("pages_active", 0) + pages.get("pages_wired_down", 0)
        total_pages = free_pages + used_pages
        
        # Convert to MB
        bytes_to_mb = lambda b: b / (1024 * 1024)
        
        # If we have total_bytes, use that for total instead of calculated
        if total_bytes > 0:
            total_memory_mb = bytes_to_mb(total_bytes)
            # Adjust free/used to match the actual total
            actual_total_bytes = total_pages * page_size
            if actual_total_bytes > 0:
                ratio = total_bytes / actual_total_bytes
                used_memory_mb = bytes_to_mb(used_pages * page_size * ratio)
                free_memory_mb = total_memory_mb - used_memory_mb
            else:
                used_memory_mb = 0
                free_memory_mb = total_memory_mb
        else:
            # Use calculated values
            total_memory_mb = bytes_to_mb(total_pages * page_size)
            used_memory_mb = bytes_to_mb(used_pages * page_size)
            free_memory_mb = bytes_to_mb(free_pages * page_size)
        
        # Calculate percentage
        used_percent = (used_memory_mb / total_memory_mb) * 100 if total_memory_mb > 0 else 0
        
        return total_memory_mb, used_memory_mb, free_memory_mb, used_percent
    
    def _parse_swap(self, swap_output: str) -> Tuple[float, float, float, float]:
        """Parse swap stats from sysctl output."""
        try:
            # Format: "total = 1024.00M used = 714.75M free = 309.25M (encrypted)"
            total_match = re.search(r"total = ([\d\.]+)([KMGT]?)", swap_output)
            used_match = re.search(r"used = ([\d\.]+)([KMGT]?)", swap_output)
            free_match = re.search(r"free = ([\d\.]+)([KMGT]?)", swap_output)
            
            def parse_size(match):
                if not match:
                    return 0
                value = float(match.group(1))
                unit = match.group(2)
                # Convert to MB
                if unit == "K":
                    return value / 1024
                elif unit == "G":
                    return value * 1024
                elif unit == "T":
                    return value * 1024 * 1024
                return value  # Already in MB
            
            total_mb = parse_size(total_match)
            used_mb = parse_size(used_match)
            free_mb = parse_size(free_match)
            percent = (used_mb / total_mb) * 100 if total_mb > 0 else 0
            
            return total_mb, used_mb, free_mb, percent
            
        except (ValueError, AttributeError):
            return 0.0, 0.0, 0.0, 0.0


class OptimizedDiskDataParser(DataParser[DiskStats]):
    """Parser for data from the optimized macOS disk provider."""
    
    def parse(self, raw_data: Dict[str, Any]) -> DiskStats:
        """Parse raw disk data into a structured format."""
        # Default values
        filesystems = []
        total_mb = 0.0
        used_mb = 0.0
        free_mb = 0.0
        
        # Check for error
        if "error" in raw_data:
            return DiskStats(filesystems, total_mb, used_mb, free_mb)
        
        # Get filesystem data
        if "parsed_filesystems" in raw_data:
            # Use pre-parsed filesystem data
            for fs in raw_data["parsed_filesystems"]:
                bytes_to_mb = lambda b: b / (1024 * 1024)
                
                # Convert bytes to MB if necessary
                fs_total_mb = bytes_to_mb(fs["size_bytes"]) if "size_bytes" in fs else 0
                fs_used_mb = bytes_to_mb(fs["used_bytes"]) if "used_bytes" in fs else 0
                fs_free_mb = bytes_to_mb(fs["available_bytes"]) if "available_bytes" in fs else 0
                fs_percent = fs.get("capacity_percent", 0.0)
                
                filesystems.append(FilesystemInfo(
                    device=fs.get("device", ""),
                    mount_point=fs.get("mount_point", ""),
                    total_mb=fs_total_mb,
                    used_mb=fs_used_mb,
                    free_mb=fs_free_mb,
                    percent_used=fs_percent
                ))
                
                # Only include physical filesystems in the totals
                if fs.get("device", "").startswith("/dev/"):
                    total_mb += fs_total_mb
                    used_mb += fs_used_mb
                    free_mb += fs_free_mb
                    
        elif "df_bytes_output" in raw_data:
            # Fall back to parsing df output
            filesystems = self._parse_df_output(raw_data["df_bytes_output"])
            
            # Calculate totals
            for fs in filesystems:
                if fs.device.startswith("/dev/"):
                    total_mb += fs.total_mb
                    used_mb += fs.used_mb
                    free_mb += fs.free_mb
        
        # Use summary if available
        if "summary" in raw_data:
            summary = raw_data["summary"]
            bytes_to_mb = lambda b: b / (1024 * 1024)
            
            total_mb = bytes_to_mb(summary.get("total_bytes", 0))
            used_mb = bytes_to_mb(summary.get("used_bytes", 0))
            free_mb = bytes_to_mb(summary.get("free_bytes", 0))
            
        return DiskStats(filesystems, total_mb, used_mb, free_mb)
    
    def _parse_df_output(self, df_output: str) -> List[FilesystemInfo]:
        """Parse filesystem information from df command output."""
        filesystems = []
        
        lines = df_output.splitlines()
        if len(lines) <= 1:
            return filesystems  # No data or just header
            
        # Process each line (skip header)
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    device = parts[0]
                    # Convert blocks to MB (assuming 1K blocks)
                    blocks = int(parts[1])
                    used = int(parts[2])
                    available = int(parts[3])
                    
                    # Parse percentage (remove % sign)
                    percent_str = parts[4]
                    if percent_str.endswith("%"):
                        percent_str = percent_str[:-1]
                    percent = float(percent_str)
                    
                    mount_point = parts[5]
                    
                    # Convert to MB
                    total_mb = blocks / 1024
                    used_mb = used / 1024
                    free_mb = available / 1024
                    
                    filesystems.append(FilesystemInfo(
                        device=device,
                        mount_point=mount_point,
                        total_mb=total_mb,
                        used_mb=used_mb,
                        free_mb=free_mb,
                        percent_used=percent
                    ))
                except (ValueError, IndexError):
                    # Skip invalid lines
                    continue
        
        return filesystems
