#!/usr/bin/env python3
"""
Interactive command-line system monitor application.

Provides real-time monitoring of CPU and network metrics on macOS systems.
"""
import sys
import argparse
import time

from cli.display import run_cpu_monitor
from cli.system_display import run_system_monitor


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="macOS System Monitor")
    
    # Update interval
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    
    # Level of detail 
    parser.add_argument(
        "-s", "--simple",
        action="store_true",
        help="Use simplified view (less detail)"
    )
    
    # Alerts
    parser.add_argument(
        "-n", "--no-alerts",
        dest="disable_alerts",
        action="store_true",
        help="Disable threshold alerts"
    )
    
    # Resource display selection options
    resource_group = parser.add_mutually_exclusive_group()
    resource_group.add_argument(
        "--cpu-only",
        action="store_true",
        help="Display only CPU metrics (default behavior)"
    )
    resource_group.add_argument(
        "--network-only",
        action="store_true",
        help="Display only network metrics"
    )
    resource_group.add_argument(
        "--all",
        action="store_true",
        help="Display all system metrics (CPU and network)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the CLI application."""
    args = parse_args()
    
    try:
        # Determine which metrics to show based on command-line arguments
        show_cpu = True
        show_network = False
        
        if args.network_only:
            show_cpu = False
            show_network = True
        elif args.all:
            show_cpu = True
            show_network = True
        # else: default to CPU only
        
        # If we're only showing CPU metrics, use the original CPU monitor
        if show_cpu and not show_network:
            run_cpu_monitor(
                update_interval=args.interval,
                detailed_view=not args.simple,
                enable_alerts=not args.disable_alerts
            )
        else:
            # Otherwise use the integrated system monitor
            run_system_monitor(
                update_interval=args.interval,
                detailed_view=not args.simple,
                enable_alerts=not args.disable_alerts,
                show_cpu=show_cpu,
                show_network=show_network
            )
            
    except KeyboardInterrupt:
        print("\nExiting System Monitor")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
