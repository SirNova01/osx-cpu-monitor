"""
Enhanced Network data provider for macOS.
"""
import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from system_metrics.providers.base import CommandExecutionProvider
 

class EnhancedMacOSNetworkDataProvider(CommandExecutionProvider):
    """Provides detailed network data on macOS including bandwidth and packet metrics."""
    
    def is_available(self) -> bool:
        """Check if this provider can be used on the current system."""
        return os.uname().sysname == "Darwin"
    
    def get_data(self) -> Dict[str, Any]:
        """Get detailed network data from the system."""
        result = {}
        
        try:
            # Get network interface details
            ifconfig_output = self.execute_command("ifconfig")
            result["ifconfig_output"] = ifconfig_output
            
            # Get network interface statistics
            netstat_int_output = self.execute_command("netstat -i")
            result["netstat_interfaces"] = netstat_int_output
            
            # Get network statistics
            netstat_output = self.execute_command("netstat -s")
            result["netstat_stats"] = netstat_output
            
            # Get current network connections
            netstat_conns = self.execute_command("netstat -an | grep -i -E 'tcp|udp'")
            result["netstat_connections"] = netstat_conns
            
            # Get active network connections with process information
            try:
                lsof_output = self.execute_command("lsof -i -P -n | grep -i -E 'listen|established'")
                result["active_connections"] = lsof_output
            except RuntimeError:
                # This might require elevated permissions
                pass
            
            # Get bandwidth usage with nettop (macOS specific)
            try:
                # Sample bandwidth for 1 second
                nettop_output = self.execute_command("nettop -L 1 -P -n -J bytes_in,bytes_out,interface -t wifi,ethernet -x")
                result["bandwidth_usage"] = nettop_output
            except RuntimeError:
                # nettop might require sudo on some systems
                pass
                
            # DNS information
            try:
                scutil_dns = self.execute_command("scutil --dns | grep 'nameserver\\|domain'")
                result["dns_config"] = scutil_dns
            except RuntimeError:
                pass
                
            # Network interfaces configuration via networksetup
            try:
                network_services = self.execute_command("networksetup -listallnetworkservices")
                result["network_services"] = network_services
                
                # Get active interfaces
                active_interfaces = []
                for line in network_services.strip().split('\n')[1:]:  # Skip the first line of output
                    service = line.strip()
                    try:
                        info = self.execute_command(f"networksetup -getinfo '{service}'")
                        active_interfaces.append((service, info))
                    except RuntimeError:
                        pass
                
                if active_interfaces:
                    result["active_interface_info"] = dict(active_interfaces)
            except RuntimeError:
                pass
                
            # Get route table
            netstat_route = self.execute_command("netstat -nr")
            result["routing_table"] = netstat_route
            
            # Wireless information (if applicable)
            try:
                airport_info = self.execute_command("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I")
                result["wifi_info"] = airport_info
            except RuntimeError:
                # Command might not be available or wireless might not be present
                pass
                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def get_interface_details(self) -> Dict[str, Any]:
        """
        Get detailed information about network interfaces.
        
        Returns a dictionary with data for each interface.
        """
        result = {}
        
        try:
            # Get list of network interfaces
            interfaces_output = self.execute_command("ifconfig -l")
            interfaces = interfaces_output.strip().split()
            result["interfaces"] = interfaces
            
            # Get details for each interface
            interface_details = {}
            for interface in interfaces:
                try:
                    details = self.execute_command(f"ifconfig {interface}")
                    interface_details[interface] = details
                except RuntimeError:
                    interface_details[interface] = "Error retrieving details"
            
            result["interface_details"] = interface_details
            
            # Get link quality and signal strength for wireless interfaces
            wireless_details = {}
            for interface in interfaces:
                if interface.startswith("en"):  # Typically wireless interfaces on macOS
                    try:
                        wifi_info = self.execute_command(
                            f"/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I")
                        if wifi_info.strip():  # If there's actual output, it's a wireless interface
                            wireless_details[interface] = wifi_info
                    except RuntimeError:
                        pass
            
            if wireless_details:
                result["wireless_details"] = wireless_details
                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def get_realtime_bandwidth(self, duration: int = 5) -> Dict[str, Any]:
        """
        Get bandwidth usage in real-time for the specified duration.
        
        Args:
            duration: Number of seconds to monitor bandwidth.
            
        Returns:
            Dictionary with bandwidth metrics.
        """
        result = {}
        
        try:
            # Try using nettop for detailed per-process network usage
            try:
                nettop_cmd = f"nettop -L {duration} -P -n -J bytes_in,bytes_out,interface,process -t wifi,ethernet -x"
                nettop_output = self.execute_command(nettop_cmd)
                result["process_bandwidth"] = nettop_output
            except RuntimeError:
                # Fallback to simpler monitoring
                pass
                
            # Use netstat to get interface statistics before and after the duration
            netstat_before = self.execute_command("netstat -ib")
            
            # Wait for the specified duration
            import time
            time.sleep(duration)
            
            netstat_after = self.execute_command("netstat -ib")
            
            result["netstat_before"] = netstat_before
            result["netstat_after"] = netstat_after
            
        except Exception as e:
            result["error"] = str(e)
            
        return result
