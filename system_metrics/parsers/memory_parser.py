"""
Parser for memory data.
"""
import re
from typing import Dict, Any, NamedTuple

from .base import DataParser


class MemoryStats(NamedTuple):
    """Structured representation of memory statistics."""
    total_memory_mb: float
    used_memory_mb: float
    free_memory_mb: float
    used_percent: float
    swap_total_mb: float
    swap_used_mb: float
    swap_free_mb: float
    swap_percent: float


class MemoryDataParser(DataParser[MemoryStats]):
    """Parser for memory data from various sources."""
    
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
        
        # Parse physical memory stats
        if "vm_stat_output" in raw_data:
            # Parse macOS vm_stat output
            total_memory_mb, used_memory_mb, free_memory_mb, used_percent = self._parse_vm_stat(
                raw_data["vm_stat_output"],
                raw_data.get("total_memory_output", "")
            )
        elif "meminfo_output" in raw_data:
            # Parse Linux /proc/meminfo output
            total_memory_mb, used_memory_mb, free_memory_mb, used_percent = self._parse_meminfo(
                raw_data["meminfo_output"]
            )
        elif "free_output" in raw_data:
            # Parse Linux free command output
            total_memory_mb, used_memory_mb, free_memory_mb, used_percent = self._parse_free(
                raw_data["free_output"]
            )
        
        # Parse swap stats
        if "swap_output" in raw_data:
            swap_total_mb, swap_used_mb, swap_free_mb, swap_percent = self._parse_swap(
                raw_data["swap_output"]
            )
        
        return MemoryStats(
            total_memory_mb, used_memory_mb, free_memory_mb, used_percent,
            swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
        )
    
    def _parse_vm_stat(self, vm_stat_output: str, total_memory_output: str) -> tuple:
        """Parse memory stats from vm_stat output (macOS)."""
        # Default values
        page_size = 4096  # Default page size in bytes
        free_pages = 0
        active_pages = 0
        inactive_pages = 0
        wired_pages = 0
        
        # Parse vm_stat output
        for line in vm_stat_output.splitlines():
            if "page size of" in line:
                # Extract page size
                match = re.search(r"page size of (\d+) bytes", line)
                if match:
                    page_size = int(match.group(1))
            elif "Pages free:" in line:
                match = re.search(r"Pages free:\s+(\d+)", line)
                if match:
                    free_pages = int(match.group(1))
            elif "Pages active:" in line:
                match = re.search(r"Pages active:\s+(\d+)", line)
                if match:
                    active_pages = int(match.group(1))
            elif "Pages inactive:" in line:
                match = re.search(r"Pages inactive:\s+(\d+)", line)
                if match:
                    inactive_pages = int(match.group(1))
            elif "Pages wired down:" in line:
                match = re.search(r"Pages wired down:\s+(\d+)", line)
                if match:
                    wired_pages = int(match.group(1))
        
        # Calculate memory values
        used_pages = active_pages + inactive_pages + wired_pages
        
        # Try to get total memory from sysctl output
        total_pages = 0
        if total_memory_output:
            try:
                total_bytes = int(total_memory_output.strip())
                total_pages = total_bytes // page_size
            except ValueError:
                total_pages = used_pages + free_pages
        else:
            total_pages = used_pages + free_pages
        
        # Convert to MB
        total_memory_mb = (total_pages * page_size) / (1024 * 1024)
        used_memory_mb = (used_pages * page_size) / (1024 * 1024)
        free_memory_mb = (free_pages * page_size) / (1024 * 1024)
        
        # Calculate percentage
        used_percent = (used_memory_mb / total_memory_mb) * 100 if total_memory_mb > 0 else 0
        
        return total_memory_mb, used_memory_mb, free_memory_mb, used_percent
    
    def _parse_meminfo(self, meminfo_output: str) -> tuple:
        """Parse memory stats from /proc/meminfo output (Linux)."""
        # Extract memory values
        mem_total = 0
        mem_free = 0
        mem_available = 0
        buffers = 0
        cached = 0
        
        for line in meminfo_output.splitlines():
            if "MemTotal:" in line:
                match = re.search(r"MemTotal:\s+(\d+)", line)
                if match:
                    mem_total = int(match.group(1))
            elif "MemFree:" in line:
                match = re.search(r"MemFree:\s+(\d+)", line)
                if match:
                    mem_free = int(match.group(1))
            elif "MemAvailable:" in line:
                match = re.search(r"MemAvailable:\s+(\d+)", line)
                if match:
                    mem_available = int(match.group(1))
            elif "Buffers:" in line:
                match = re.search(r"Buffers:\s+(\d+)", line)
                if match:
                    buffers = int(match.group(1))
            elif "Cached:" in line:
                # Only match the main Cached line, not SReclaimable
                if ":" in line and line.split(":")[0].strip() == "Cached":
                    match = re.search(r"Cached:\s+(\d+)", line)
                    if match:
                        cached = int(match.group(1))
        
        # Convert from KB to MB
        total_memory_mb = mem_total / 1024
        
        # If MemAvailable is available, use it (modern Linux)
        if mem_available > 0:
            free_memory_mb = mem_available / 1024
            used_memory_mb = total_memory_mb - free_memory_mb
        else:
            # Traditional calculation
            free_memory_mb = (mem_free + buffers + cached) / 1024
            used_memory_mb = total_memory_mb - free_memory_mb
        
        # Calculate percentage
        used_percent = (used_memory_mb / total_memory_mb) * 100 if total_memory_mb > 0 else 0
        
        return total_memory_mb, used_memory_mb, free_memory_mb, used_percent
    
    def _parse_free(self, free_output: str) -> tuple:
        """Parse memory stats from free command output (Linux)."""
        # Parse free output (looking for the 'Mem:' line)
        lines = free_output.splitlines()
        for line in lines:
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        # Format: Mem: total used free shared buff/cache available
                        total = int(parts[1])
                        used = int(parts[2])
                        free = int(parts[3])
                        
                        # Convert bytes to MB
                        total_memory_mb = total / (1024 * 1024)
                        used_memory_mb = used / (1024 * 1024)
                        free_memory_mb = free / (1024 * 1024)
                        
                        # Calculate percentage
                        used_percent = (used_memory_mb / total_memory_mb) * 100 if total_memory_mb > 0 else 0
                        
                        return total_memory_mb, used_memory_mb, free_memory_mb, used_percent
                    except (ValueError, IndexError):
                        pass
        
        return 0.0, 0.0, 0.0, 0.0
    
    def _parse_swap(self, swap_output: str) -> tuple:
        """Parse swap stats from various sources."""
        # Default values
        swap_total_mb = 0.0
        swap_used_mb = 0.0
        swap_free_mb = 0.0
        swap_percent = 0.0
        
        # Try to parse macOS sysctl output format
        # Example: "total = 1024.00M used = 714.75M free = 309.25M (encrypted)"
        try:
            matches = re.findall(r"(\d+\.\d+)M", swap_output)
            if len(matches) >= 3:
                swap_total_mb = float(matches[0])
                swap_used_mb = float(matches[1])
                swap_free_mb = float(matches[2])
                swap_percent = (swap_used_mb / swap_total_mb) * 100 if swap_total_mb > 0 else 0
                return swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
        except (ValueError, IndexError):
            pass
        
        # Try to parse Linux /proc/swaps format
        # Example: "Filename Type Size Used Priority"
        try:
            lines = swap_output.splitlines()
            if len(lines) > 1:  # Skip header
                total = 0
                used = 0
                
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        total += int(parts[2])
                        used += int(parts[3])
                
                # Convert KB to MB
                swap_total_mb = total / 1024
                swap_used_mb = used / 1024
                swap_free_mb = swap_total_mb - swap_used_mb
                swap_percent = (swap_used_mb / swap_total_mb) * 100 if swap_total_mb > 0 else 0
                
                return swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
        except (ValueError, IndexError):
            pass
        
        return swap_total_mb, swap_used_mb, swap_free_mb, swap_percent
