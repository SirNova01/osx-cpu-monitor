"""
Enhanced Network monitoring service for macOS.

This module provides detailed network metrics including interface statistics,
bandwidth usage, and connection information.
"""
import time
from threading import Thread, Lock
from typing import Dict, List, Optional, Tuple, Any, Set

from system_metrics.base import Metric, MetricsCollector
from .providers.base import SystemDataProvider
from .parsers.base import DataParser


class EnhancedNetworkMonitor:
    """
    Enhanced Network monitor with detailed metrics and real-time updates.
    
    Features:
    - Per-interface network statistics (bytes/packets sent and received)
    - Bandwidth usage monitoring (bytes per second in/out)
    - Active connection tracking (TCP/UDP, established/listening)
    - WiFi signal strength and connection details
    - Real-time updates with configurable intervals
    - Thread-safe access to metrics data
    """
    
    def __init__(self, provider: SystemDataProvider, parser: DataParser, update_interval: float = 5.0):
        """
        Initialize the Network monitor.
        
        Args:
            provider: The system data provider to use
            parser: The parser for Network data
            update_interval: Update interval in seconds (default: 5.0)
        """
        self._provider = provider
        self._parser = parser
        self._update_interval = update_interval
        
        # Initialize metrics storage
        self._metrics: Dict[str, Metric] = {
            # Overall network metrics
            "total_interfaces": Metric("total_interfaces", "Total number of network interfaces"),
            "active_interfaces": Metric("active_interfaces", "Number of active network interfaces"),
            "total_rx_bytes": Metric("total_rx_bytes", "Total bytes received"),
            "total_tx_bytes": Metric("total_tx_bytes", "Total bytes transmitted"),
            "total_rx_packets": Metric("total_rx_packets", "Total packets received"),
            "total_tx_packets": Metric("total_tx_packets", "Total packets transmitted"),
            "total_errors": Metric("total_errors", "Total network errors"),
            
            # Bandwidth metrics
            "rx_bytes_per_sec": Metric("rx_bytes_per_sec", "Bytes received per second"),
            "tx_bytes_per_sec": Metric("tx_bytes_per_sec", "Bytes transmitted per second"),
            
            # Connection metrics
            "tcp_connections": Metric("tcp_connections", "Number of TCP connections"),
            "udp_connections": Metric("udp_connections", "Number of UDP connections"),
            "total_connections": Metric("total_connections", "Total number of network connections"),
            "established_connections": Metric("established_connections", "Number of established connections"),
            "listening_ports": Metric("listening_ports", "Number of listening ports"),
        }
        
        # WiFi metrics
        self._wifi_metrics: Dict[str, Metric] = {
            "wifi_connected": Metric("wifi_connected", "WiFi connection status"),
            "wifi_ssid": Metric("wifi_ssid", "Connected WiFi network SSID"),
            "wifi_signal_strength": Metric("wifi_signal_strength", "WiFi signal strength (RSSI)"),
            "wifi_noise": Metric("wifi_noise", "WiFi noise level"),
            "wifi_channel": Metric("wifi_channel", "WiFi channel"),
            "wifi_tx_rate": Metric("wifi_tx_rate", "WiFi transmission rate"),
        }
        
        # Per-interface metrics (will be populated during first update)
        self._interface_metrics: Dict[str, Metric] = {}
        
        # Keep track of known interfaces
        self._known_interfaces: Set[str] = set()
        
        # Concurrency control
        self._lock = Lock()
        self._running = False
        self._update_thread: Optional[Thread] = None
        self._latest_data: Optional[Dict[str, Any]] = {}
        
        # Remember last update time for bandwidth calculation
        self._last_update_time = time.time()
        self._prev_rx_bytes = {}
        self._prev_tx_bytes = {}
    
    def start(self) -> None:
        """Start the background updater thread."""
        if self._running:
            return
        
        self._running = True
        self._update_thread = Thread(target=self._updater_loop, daemon=True)
        self._update_thread.start()
    
    def stop(self) -> None:
        """Stop the background updater thread."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=self._update_interval + 1)
            self._update_thread = None
    
    def update_now(self) -> None:
        """Force an immediate update of network metrics."""
        self._update_metrics()
    
    def _updater_loop(self) -> None:
        """Background thread to update metrics at regular intervals."""
        while self._running:
            try:
                self._update_metrics()
            except Exception as e:
                print(f"Error updating network metrics: {e}")
            
            # Sleep for the update interval
            time.sleep(self._update_interval)
    
    def _update_metrics(self) -> None:
        """Update all network metrics."""
        try:
            # Get raw data from provider
            raw_data = self._provider.get_data()
            
            # Parse the data - ensure result is a dict even if parser returns something else
            network_stats = self._parser.parse(raw_data)
            if not isinstance(network_stats, dict):
                network_stats = {"interfaces": {}}
            
            # Calculate elapsed time since last update (for bandwidth calculation)
            current_time = time.time()
            elapsed_time = current_time - self._last_update_time
            self._last_update_time = current_time
            
            with self._lock:
                self._latest_data = network_stats
                
                # Ensure interfaces key exists
                if "interfaces" not in network_stats:
                    network_stats["interfaces"] = {}
                
                # Handle case where interfaces is a list rather than a dict
                if isinstance(network_stats["interfaces"], list):
                    interface_dict = {}
                    for interface in network_stats["interfaces"]:
                        if "name" in interface:
                            interface_name = interface["name"]
                            interface_dict[interface_name] = interface
                    network_stats["interfaces"] = interface_dict
                
                # Update overall network metrics
                total_interfaces = len(network_stats["interfaces"])
                active_interfaces = sum(1 for interface in network_stats["interfaces"].values() 
                                    if interface.get("status", "").lower() == "active")
                                    
                # Calculate total metrics
                total_rx_bytes = 0
                total_tx_bytes = 0
                total_rx_packets = 0
                total_tx_packets = 0
                total_errors = 0
                
                for interface in network_stats["interfaces"].values():
                    total_rx_bytes += interface.get("rx_bytes", 0)
                    total_tx_bytes += interface.get("tx_bytes", 0)
                    total_rx_packets += interface.get("rx_packets", 0)
                    total_tx_packets += interface.get("tx_packets", 0)
                    total_errors += interface.get("rx_errors", 0) + interface.get("tx_errors", 0)
                
                self._metrics["total_interfaces"].add_value(total_interfaces)
                self._metrics["active_interfaces"].add_value(active_interfaces)
                self._metrics["total_rx_bytes"].add_value(total_rx_bytes, "bytes")
                self._metrics["total_tx_bytes"].add_value(total_tx_bytes, "bytes")
                self._metrics["total_rx_packets"].add_value(total_rx_packets, "packets")
                self._metrics["total_tx_packets"].add_value(total_tx_packets, "packets")
                self._metrics["total_errors"].add_value(total_errors, "errors")
                
                # Calculate bandwidth based on previous values
                rx_bytes_per_sec = 0
                tx_bytes_per_sec = 0
                
                # Use bandwidth calculation if available in parsed data
                if "bandwidth" in network_stats:
                    rx_bytes_per_sec = network_stats["bandwidth"].get("in_bytes_per_sec", 0)
                    tx_bytes_per_sec = network_stats["bandwidth"].get("out_bytes_per_sec", 0)
                else:
                    # Calculate it ourselves from the change in byte counts
                    if self._prev_rx_bytes and self._prev_tx_bytes and elapsed_time > 0:
                        # Calculate per-interface bandwidth
                        interface_rx_bandwidth = {}
                        interface_tx_bandwidth = {}
                        
                        for interface_name, interface_data in network_stats["interfaces"].items():
                            curr_rx = interface_data.get("rx_bytes", 0)
                            curr_tx = interface_data.get("tx_bytes", 0)
                            
                            if interface_name in self._prev_rx_bytes and interface_name in self._prev_tx_bytes:
                                rx_diff = curr_rx - self._prev_rx_bytes[interface_name]
                                tx_diff = curr_tx - self._prev_tx_bytes[interface_name]
                                
                                # Handle counter reset
                                if rx_diff >= 0:
                                    rx_bytes_per_sec += rx_diff / elapsed_time
                                    interface_rx_bandwidth[interface_name] = rx_diff / elapsed_time
                                if tx_diff >= 0:
                                    tx_bytes_per_sec += tx_diff / elapsed_time
                                    interface_tx_bandwidth[interface_name] = tx_diff / elapsed_time
                    
                    # Store current values for next calculation
                    self._prev_rx_bytes = {
                        interface_name: interface_data.get("rx_bytes", 0)
                        for interface_name, interface_data in network_stats["interfaces"].items()
                    }
                    self._prev_tx_bytes = {
                        interface_name: interface_data.get("tx_bytes", 0)
                        for interface_name, interface_data in network_stats["interfaces"].items()
                    }
                
                # Update bandwidth metrics
                self._metrics["rx_bytes_per_sec"].add_value(rx_bytes_per_sec, "B/s")
                self._metrics["tx_bytes_per_sec"].add_value(tx_bytes_per_sec, "B/s")
            
                # Update connection metrics if available
                if "connections" in network_stats:
                    connections = network_stats["connections"]
                    self._metrics["tcp_connections"].add_value(connections.get("tcp", 0))
                    self._metrics["udp_connections"].add_value(connections.get("udp", 0))
                    self._metrics["total_connections"].add_value(connections.get("total", 0))
                    self._metrics["established_connections"].add_value(connections.get("established", 0))
                    self._metrics["listening_ports"].add_value(connections.get("listening", 0))
            
                # Update WiFi metrics if available
                if "wifi" in network_stats and network_stats["wifi"]:
                    wifi = network_stats["wifi"]
                    self._wifi_metrics["wifi_connected"].add_value(True)
                    self._wifi_metrics["wifi_ssid"].add_value(wifi.get("ssid", ""))
                    self._wifi_metrics["wifi_signal_strength"].add_value(wifi.get("rssi", 0), "dBm")
                    self._wifi_metrics["wifi_noise"].add_value(wifi.get("noise", 0), "dBm")
                    self._wifi_metrics["wifi_channel"].add_value(wifi.get("channel", ""))
                    self._wifi_metrics["wifi_tx_rate"].add_value(wifi.get("tx_rate", 0), "Mbps")
                else:
                    self._wifi_metrics["wifi_connected"].add_value(False)
            
                # Update per-interface metrics
                self._update_interface_metrics(network_stats["interfaces"])
            
        except Exception as e:
            print(f"Error in _update_metrics: {e}")
    
    def _update_interface_metrics(self, interfaces: Dict[str, Dict[str, Any]]) -> None:
        """Update per-interface network metrics."""
        # Keep track of current interfaces
        current_interfaces = set(interfaces.keys())
        
        for interface_name, interface_data in interfaces.items():
            # Create interface metrics if they don't exist
            interface_prefix = f"if_{interface_name}"
            if interface_name not in self._known_interfaces:
                self._known_interfaces.add(interface_name)
                self._interface_metrics[f"{interface_prefix}_status"] = Metric(
                    f"{interface_prefix}_status", f"Interface {interface_name} status")
                self._interface_metrics[f"{interface_prefix}_rx_bytes"] = Metric(
                    f"{interface_prefix}_rx_bytes", f"Interface {interface_name} bytes received")
                self._interface_metrics[f"{interface_prefix}_tx_bytes"] = Metric(
                    f"{interface_prefix}_tx_bytes", f"Interface {interface_name} bytes transmitted")
                self._interface_metrics[f"{interface_prefix}_rx_packets"] = Metric(
                    f"{interface_prefix}_rx_packets", f"Interface {interface_name} packets received")
                self._interface_metrics[f"{interface_prefix}_tx_packets"] = Metric(
                    f"{interface_prefix}_tx_packets", f"Interface {interface_name} packets transmitted")
                self._interface_metrics[f"{interface_prefix}_errors"] = Metric(
                    f"{interface_prefix}_errors", f"Interface {interface_name} errors")
                self._interface_metrics[f"{interface_prefix}_mtu"] = Metric(
                    f"{interface_prefix}_mtu", f"Interface {interface_name} MTU")
            
            # Update interface metrics
            self._interface_metrics[f"{interface_prefix}_status"].add_value(interface_data.get("status", "unknown"))
            self._interface_metrics[f"{interface_prefix}_rx_bytes"].add_value(interface_data.get("rx_bytes", 0), "bytes")
            self._interface_metrics[f"{interface_prefix}_tx_bytes"].add_value(interface_data.get("tx_bytes", 0), "bytes")
            self._interface_metrics[f"{interface_prefix}_rx_packets"].add_value(interface_data.get("rx_packets", 0), "packets")
            self._interface_metrics[f"{interface_prefix}_tx_packets"].add_value(interface_data.get("tx_packets", 0), "packets")
            
            # Errors can be stored in different ways depending on the parser
            rx_errors = interface_data.get("rx_errors", 0)
            tx_errors = interface_data.get("tx_errors", 0)
            total_errors = rx_errors + tx_errors
            
            self._interface_metrics[f"{interface_prefix}_errors"].add_value(total_errors, "errors")
            self._interface_metrics[f"{interface_prefix}_mtu"].add_value(interface_data.get("mtu", 1500), "bytes")
            
            # Add IP information if available
            ipv4_addresses = []
            if "ipv4_addresses" in interface_data:
                ipv4_addresses = interface_data["ipv4_addresses"]
            elif "ipv4" in interface_data:
                if isinstance(interface_data["ipv4"], list):
                    ipv4_addresses = [ip.get("address", "") for ip in interface_data["ipv4"] if "address" in ip]
            
            if ipv4_addresses:
                if f"{interface_prefix}_ipv4" not in self._interface_metrics:
                    self._interface_metrics[f"{interface_prefix}_ipv4"] =  Metric(
                        f"{interface_prefix}_ipv4", f"Interface {interface_name} IPv4 addresses")
                self._interface_metrics[f"{interface_prefix}_ipv4"].add_value(",".join(ipv4_addresses))
                
    def get_metrics(self) -> Dict[str, Metric]:
        """Get all network metrics."""
        with self._lock:
            # Combine all metrics dictionaries
            all_metrics = {}
            all_metrics.update(self._metrics)
            all_metrics.update(self._wifi_metrics)
            all_metrics.update(self._interface_metrics)
            return all_metrics
    
    def get_interface_metrics(self) -> Dict[str, Metric]:
        """Get per-interface network metrics."""
        with self._lock:
            return self._interface_metrics.copy()
    
    def get_wifi_metrics(self) -> Dict[str, Metric]:
        """Get WiFi-specific metrics."""
        with self._lock:
            return self._wifi_metrics.copy()
    
    def get_bandwidth_usage(self) -> Dict[str, float]:
        """Get current bandwidth usage."""
        with self._lock:
            return {
                "rx_bytes_per_sec": self._metrics["rx_bytes_per_sec"].current_value.value 
                    if self._metrics["rx_bytes_per_sec"].current_value else 0.0,
                "tx_bytes_per_sec": self._metrics["tx_bytes_per_sec"].current_value.value 
                    if self._metrics["tx_bytes_per_sec"].current_value else 0.0,
            }
    
    def get_connection_stats(self) -> Dict[str, int]:
        """Get connection statistics."""
        with self._lock:
            return {
                "tcp": self._metrics["tcp_connections"].current_value.value 
                    if self._metrics["tcp_connections"].current_value else 0,
                "udp": self._metrics["udp_connections"].current_value.value 
                    if self._metrics["udp_connections"].current_value else 0,
                "total": self._metrics["total_connections"].current_value.value 
                    if self._metrics["total_connections"].current_value else 0,
                "established": self._metrics["established_connections"].current_value.value 
                    if self._metrics["established_connections"].current_value else 0,
                "listening": self._metrics["listening_ports"].current_value.value 
                    if self._metrics["listening_ports"].current_value else 0,
            }
    
    def get_wifi_details(self) -> Dict[str, Any]:
        """Get detailed WiFi information if available."""
        with self._lock:
            if not self._wifi_metrics["wifi_connected"].current_value or \
               not self._wifi_metrics["wifi_connected"].current_value.value:
                return {"connected": False}
                
            return {
                "connected": True,
                "ssid": self._wifi_metrics["wifi_ssid"].current_value.value 
                    if self._wifi_metrics["wifi_ssid"].current_value else "",
                "signal_strength": self._wifi_metrics["wifi_signal_strength"].current_value.value 
                    if self._wifi_metrics["wifi_signal_strength"].current_value else 0,
                "noise": self._wifi_metrics["wifi_noise"].current_value.value 
                    if self._wifi_metrics["wifi_noise"].current_value else 0,
                "channel": self._wifi_metrics["wifi_channel"].current_value.value 
                    if self._wifi_metrics["wifi_channel"].current_value else "",
                "tx_rate": self._wifi_metrics["wifi_tx_rate"].current_value.value 
                    if self._wifi_metrics["wifi_tx_rate"].current_value else 0,
            }
    
    def get_interface_details(self) -> List[Dict[str, Any]]:
        """Get detailed information for all interfaces."""
        with self._lock:
            if not self._latest_data or "interfaces" not in self._latest_data:
                return []
                
            result = []
            for interface_name, interface_data in self._latest_data["interfaces"].items():
                # Format interface data for display
                interface_info = {
                    "name": interface_name,
                    "status": interface_data.get("status", "unknown"),
                    "mac_address": interface_data.get("mac_address", ""),
                    "rx_bytes": interface_data.get("rx_bytes", 0),
                    "tx_bytes": interface_data.get("tx_bytes", 0),
                    "rx_packets": interface_data.get("rx_packets", 0),
                    "tx_packets": interface_data.get("tx_packets", 0),
                    "rx_errors": interface_data.get("rx_errors", 0),
                    "tx_errors": interface_data.get("tx_errors", 0),
                    "errors": interface_data.get("rx_errors", 0) + interface_data.get("tx_errors", 0),
                    "mtu": interface_data.get("mtu", 1500)
                }
                
                # Handle IPv4 addresses in different formats
                ipv4_addresses = []
                if "ipv4_addresses" in interface_data:
                    ipv4_addresses = interface_data["ipv4_addresses"]
                elif "ipv4" in interface_data:
                    if isinstance(interface_data["ipv4"], list):
                        ipv4_addresses = [ip.get("address", "") 
                                        for ip in interface_data["ipv4"] 
                                        if isinstance(ip, dict) and "address" in ip]
                
                interface_info["ipv4_addresses"] = ipv4_addresses
                
                # Handle IPv6 addresses in different formats
                ipv6_addresses = []
                if "ipv6_addresses" in interface_data:
                    ipv6_addresses = interface_data["ipv6_addresses"]
                elif "ipv6" in interface_data:
                    if isinstance(interface_data["ipv6"], list):
                        ipv6_addresses = [ip.get("address", "") 
                                        for ip in interface_data["ipv6"] 
                                        if isinstance(ip, dict) and "address" in ip]
                
                interface_info["ipv6_addresses"] = ipv6_addresses
                
                # Add speed and duplex info if available
                if "speed_mbps" in interface_data:
                    interface_info["speed_mbps"] = interface_data["speed_mbps"]
                if "duplex" in interface_data:
                    interface_info["duplex"] = interface_data["duplex"]
                    
                result.append(interface_info)
                
            return result
    
    
    def get_network_processes(self) -> List[Dict[str, Any]]:
        """Get information about processes using the network."""
        # This is a placeholder - actual implementation would depend on
        # how process network usage is tracked in the system
        return []


class EnhancedNetworkMetricsCollector(MetricsCollector):
    """
    Network metrics collector compatible with the original metrics collection framework,
    but providing enhanced network monitoring capabilities.
    """
    
    def __init__(self, network_monitor: EnhancedNetworkMonitor):
        """
        Initialize the enhanced network metrics collector.
        
        Args:
            network_monitor: An initialized EnhancedNetworkMonitor instance
        """
        super().__init__()
        self._network_monitor = network_monitor
        
        # Initialize the network monitor if it's not already running
        if not self._network_monitor._running:
            self._network_monitor.start()
    
    def collect(self) -> Dict[str, Metric]:
        """Collect network metrics using the enhanced network monitor."""
        # Update network metrics
        self._network_monitor.update_now()
        
        # Get all metrics from the monitor
        all_metrics = self._network_monitor.get_metrics()
        
        # Update our metrics dictionary
        self._metrics = all_metrics
        
        return self._metrics
    
    def get_network_bandwidth(self) -> Dict[str, float]:
        """Get current network bandwidth usage."""
        return self._network_monitor.get_bandwidth_usage()
    
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get information about all network interfaces."""
        return self._network_monitor.get_interface_details()
    
    def get_connection_stats(self) -> Dict[str, int]:
        """Get network connection statistics."""
        return self._network_monitor.get_connection_stats()
    
    def get_wifi_info(self) -> Dict[str, Any]:
        """Get WiFi connection information if available."""
        return self._network_monitor.get_wifi_details()
    
    def get_total_data_transferred(self) -> Dict[str, int]:
        """Get total data transferred (bytes in/out)."""
        rx_metric = self._metrics.get("total_rx_bytes")
        tx_metric = self._metrics.get("total_tx_bytes")
        
        return {
            "received_bytes": rx_metric.current_value.value if rx_metric and rx_metric.current_value else 0,
            "sent_bytes": tx_metric.current_value.value if tx_metric and tx_metric.current_value else 0,
        }
    

