"""
Parser for disk data.
"""
import re
from typing import Dict, Any, List, NamedTuple

from .base import DataParser


class FilesystemInfo(NamedTuple):
    """Information about a single filesystem."""
    device: str
    mount_point: str
    total_mb: float
    used_mb: float
    free_mb: float
    percent_used: float


class DiskStats(NamedTuple):
    """Structured representation of disk statistics."""
    filesystems: List[FilesystemInfo]
    total_mb: float
    used_mb: float
    free_mb: float


class DiskDataParser(DataParser[DiskStats]):
    """Parser for disk data from various sources."""
    
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
        
        # Parse df output
        if "df_output" in raw_data:
            filesystems = self._parse_df_output(raw_data["df_output"])
            
            # Calculate totals (only for real filesystems)
            for fs in filesystems:
                if fs.device.startswith("/dev/"):
                    total_mb += fs.total_mb
                    used_mb += fs.used_mb
                    free_mb += fs.free_mb
        
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
