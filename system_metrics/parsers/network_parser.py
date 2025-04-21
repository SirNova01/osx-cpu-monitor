"""
Parser for network data on macOS systems.
"""
import re
from typing import Dict, Any, List, Optional

from system_metrics.parsers.base import DataParser


class MacOSNetworkParser(DataParser):
    """Parser for network data from macOS systems."""

    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw network data into structured metrics.
        
        Args:
            raw_data: Raw data collected from EnhancedMacOSNetworkDataProvider.
            
        Returns:
            Dictionary with structured network metrics.
        """
        result = {
            "interfaces": {},
            "stats": {
                "total_sent": 0,
                "total_received": 0,
                "packets_in": 0,
                "packets_out": 0,
                "errors_in": 0,
                "errors_out": 0,
                "active_connections": 0
            },
            "wifi": {},
            "connections": {
                "tcp": 0,
                "udp": 0,
                "listening": 0,
                "established": 0
            },
            "routing": {},
            "bandwidth": {
                "in_bytes_per_sec": 0,
                "out_bytes_per_sec": 0
            }
        }
        
        # Parse interface data
        if "ifconfig_output" in raw_data:
            interfaces = self._parse_ifconfig(raw_data["ifconfig_output"])
            result["interfaces"] = interfaces
        
        # Parse interface statistics
        if "netstat_interfaces" in raw_data:
            self._parse_netstat_interfaces(raw_data["netstat_interfaces"], result)
        
        # Parse connection data
        if "netstat_connections" in raw_data:
            self._parse_connections(raw_data["netstat_connections"], result)
        
        # Parse wireless data if available
        if "wifi_info" in raw_data:
            self._parse_wifi_info(raw_data["wifi_info"], result)
        
        # Parse bandwidth data if available
        if "bandwidth_usage" in raw_data:
            self._parse_bandwidth(raw_data["bandwidth_usage"], result)
        
        # Add additional interface details
        if "interface_details" in raw_data.get("interface_details", {}):
            for interface, details in raw_data["interface_details"].items():
                if interface in result["interfaces"]:
                    result["interfaces"][interface]["details"] = self._extract_interface_details(details)
        
        # Calculate real-time bandwidth if before/after snapshots are available
        if "netstat_before" in raw_data and "netstat_after" in raw_data:
            bandwidth = self._calculate_bandwidth(
                raw_data["netstat_before"], 
                raw_data["netstat_after"]
            )
            if bandwidth:
                result["bandwidth"] = bandwidth
        
        return result

    def _parse_ifconfig(self, ifconfig_output: str) -> Dict[str, Any]:
        """Parse ifconfig output to get interface details."""
        interfaces = {}
        current_interface = None
        
        for line in ifconfig_output.splitlines():
            # New interface section starts with interface name
            if not line.startswith('\t'):
                match = re.match(r'^([a-zA-Z0-9]+):', line)
                if match:
                    current_interface = match.group(1)
                    interfaces[current_interface] = {
                        "status": "unknown",
                        "mac_address": "",
                        "ipv4": [],
                        "ipv6": [],
                        "mtu": 0,
                        "metrics": {
                            "rx_bytes": 0,
                            "rx_packets": 0,
                            "tx_bytes": 0,
                            "tx_packets": 0,
                            "rx_errors": 0,
                            "tx_errors": 0,
                        }
                    }
            elif current_interface:
                # Status info
                if "status:" in line.lower():
                    status_match = re.search(r'status: (\w+)', line)
                    if status_match:
                        interfaces[current_interface]["status"] = status_match.group(1)

                # MAC address
                ether_match = re.search(r'ether (.+?)\s', line)
                if ether_match:
                    interfaces[current_interface]["mac_address"] = ether_match.group(1)
                
                # IPv4 address
                inet_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                if inet_match:
                    netmask_match = re.search(r'netmask (0x[a-f0-9]+)', line)
                    netmask = netmask_match.group(1) if netmask_match else ""
                    ipv4_entry = {
                        "address": inet_match.group(1),
                        "netmask": netmask
                    }
                    interfaces[current_interface]["ipv4"].append(ipv4_entry)
                
                # IPv6 address
                inet6_match = re.search(r'inet6 ([a-f0-9:]+)', line)
                if inet6_match:
                    prefixlen_match = re.search(r'prefixlen (\d+)', line)
                    prefixlen = prefixlen_match.group(1) if prefixlen_match else ""
                    ipv6_entry = {
                        "address": inet6_match.group(1),
                        "prefixlen": prefixlen
                    }
                    interfaces[current_interface]["ipv6"].append(ipv6_entry)
                
                # MTU
                mtu_match = re.search(r'mtu (\d+)', line)
                if mtu_match:
                    interfaces[current_interface]["mtu"] = int(mtu_match.group(1))
                
                # Traffic statistics
                if "bytes" in line:
                    rx_bytes_match = re.search(r'RX bytes:(\d+)', line)
                    tx_bytes_match = re.search(r'TX bytes:(\d+)', line)
                    
                    if rx_bytes_match:
                        interfaces[current_interface]["metrics"]["rx_bytes"] = int(rx_bytes_match.group(1))
                    if tx_bytes_match:
                        interfaces[current_interface]["metrics"]["tx_bytes"] = int(tx_bytes_match.group(1))
        
        return interfaces
    
    def _parse_netstat_interfaces(self, netstat_output: str, result: Dict[str, Any]) -> None:
        """Parse netstat -i output to get interface statistics."""
        lines = netstat_output.strip().split('\n')
        if len(lines) < 2:
            return
        
        # Skip header row
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 5:
                interface_name = parts[0].rstrip('*')
                
                # Find the right indices by checking header
                header = lines[0].lower()
                ipkts_idx = header.split().index('ipkts') if 'ipkts' in header.split() else 4
                ierrs_idx = header.split().index('ierrs') if 'ierrs' in header.split() else 5
                opkts_idx = header.split().index('opkts') if 'opkts' in header.split() else 6
                oerrs_idx = header.split().index('oerrs') if 'oerrs' in header.split() else 7
                
                if ipkts_idx < len(parts) and interface_name in result["interfaces"]:
                    try:
                        result["interfaces"][interface_name]["metrics"]["rx_packets"] = int(parts[ipkts_idx])
                        result["stats"]["packets_in"] += int(parts[ipkts_idx])
                    except (ValueError, IndexError):
                        pass
                
                if ierrs_idx < len(parts) and interface_name in result["interfaces"]:
                    try:
                        result["interfaces"][interface_name]["metrics"]["rx_errors"] = int(parts[ierrs_idx])
                        result["stats"]["errors_in"] += int(parts[ierrs_idx])
                    except (ValueError, IndexError):
                        pass
                        
                if opkts_idx < len(parts) and interface_name in result["interfaces"]:
                    try:
                        result["interfaces"][interface_name]["metrics"]["tx_packets"] = int(parts[opkts_idx])
                        result["stats"]["packets_out"] += int(parts[opkts_idx])
                    except (ValueError, IndexError):
                        pass
                        
                if oerrs_idx < len(parts) and interface_name in result["interfaces"]:
                    try:
                        result["interfaces"][interface_name]["metrics"]["tx_errors"] = int(parts[oerrs_idx])
                        result["stats"]["errors_out"] += int(parts[oerrs_idx])
                    except (ValueError, IndexError):
                        pass
    
    def _parse_connections(self, connections_output: str, result: Dict[str, Any]) -> None:
        """Parse netstat connection data to get connection statistics."""
        for line in connections_output.splitlines():
            line = line.lower()
            if 'tcp' in line:
                result["connections"]["tcp"] += 1
            if 'udp' in line:
                result["connections"]["udp"] += 1
            if 'listen' in line:
                result["connections"]["listening"] += 1
            if 'established' in line:
                result["connections"]["established"] += 1
        
        result["connections"]["total"] = result["connections"]["tcp"] + result["connections"]["udp"]
        result["stats"]["active_connections"] = result["connections"]["established"]
    
    def _parse_wifi_info(self, wifi_output: str, result: Dict[str, Any]) -> None:
        """Parse airport command output to get WiFi information."""
        wifi_data = {}
        
        for line in wifi_output.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                wifi_data[key] = value
        
        if wifi_data:
            result["wifi"] = {
                "interface": wifi_data.get("agrCtlRSSI", ""),
                "ssid": wifi_data.get("SSID", ""),
                "bssid": wifi_data.get("BSSID", ""),
                "channel": wifi_data.get("channel", ""),
                "rssi": int(wifi_data.get("agrCtlRSSI", "0")) if wifi_data.get("agrCtlRSSI", "").strip("-").isdigit() else 0,
                "noise": int(wifi_data.get("agrCtlNoise", "0")) if wifi_data.get("agrCtlNoise", "").strip("-").isdigit() else 0,
                "tx_rate": wifi_data.get("lastTxRate", ""),
                "security": wifi_data.get("link auth", "")
            }
    
    def _parse_bandwidth(self, bandwidth_output: str, result: Dict[str, Any]) -> None:
        """Parse nettop output to get bandwidth information."""
        total_in = 0
        total_out = 0
        
        for line in bandwidth_output.splitlines():
            parts = line.split(',')
            if len(parts) >= 3:
                try:
                    # nettop output varies, so try to extract values carefully
                    bytes_in = int(parts[0]) if parts[0].isdigit() else 0
                    bytes_out = int(parts[1]) if parts[1].isdigit() else 0
                    total_in += bytes_in
                    total_out += bytes_out
                except (ValueError, IndexError):
                    continue
        
        # These are just instantaneous values, not per-second rates
        result["bandwidth"]["total_in"] = total_in
        result["bandwidth"]["total_out"] = total_out
    
    def _extract_interface_details(self, interface_details: str) -> Dict[str, Any]:
        """Extract additional details for a network interface."""
        details = {}
        
        media_match = re.search(r'media: (.+?) [(<]', interface_details)
        if media_match:
            details["media"] = media_match.group(1)
        
        duplex_match = re.search(r'(half|full)-duplex', interface_details)
        if duplex_match:
            details["duplex"] = duplex_match.group(1)
        
        speed_match = re.search(r'(\d+)(baseT|Gbps|Mbps)', interface_details)
        if speed_match:
            speed = speed_match.group(1)
            unit = speed_match.group(2)
            details["speed"] = f"{speed} {unit}"
        
        return details
    
    def _calculate_bandwidth(self, before: str, after: str) -> Dict[str, Any]:
        """Calculate bandwidth based on before and after netstat snapshots."""
        result = {
            "interfaces": {},
            "in_bytes_per_sec": 0,
            "out_bytes_per_sec": 0
        }
        
        # Helper function to parse netstat -ib output
        def parse_netstat_ib(output):
            interfaces = {}
            lines = output.strip().split('\n')
            if len(lines) < 2:
                return interfaces
            
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 10:
                    interface = parts[0].rstrip('*')
                    try:
                        ibytes = int(parts[6])
                        obytes = int(parts[9])
                        interfaces[interface] = {"ibytes": ibytes, "obytes": obytes}
                    except (ValueError, IndexError):
                        continue
            
            return interfaces
        
        before_interfaces = parse_netstat_ib(before)
        after_interfaces = parse_netstat_ib(after)
        
        # Calculate differences for each interface
        for interface in after_interfaces:
            if interface in before_interfaces:
                ibytes_diff = after_interfaces[interface]["ibytes"] - before_interfaces[interface]["ibytes"]
                obytes_diff = after_interfaces[interface]["obytes"] - before_interfaces[interface]["obytes"]
                
                # Only count positive differences (could be negative if counters reset)
                if ibytes_diff > 0:
                    result["in_bytes_per_sec"] += ibytes_diff
                if obytes_diff > 0:
                    result["out_bytes_per_sec"] += obytes_diff
                
                result["interfaces"][interface] = {
                    "in_bytes_per_sec": max(0, ibytes_diff),
                    "out_bytes_per_sec": max(0, obytes_diff)
                }
        
        # Convert to per-second rates (assuming snapshots were taken 1 second apart)
        # Note: The actual time difference should be passed if available for more accurate rates
        return result
