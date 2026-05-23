#!/usr/bin/env python3
"""
Network Monitoring Script for Sakura

This script monitors network connections to ensure no unauthorized
external communication is happening.
"""

import time
import socket
import subprocess
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '::1',
    'gitlab.com',
    '35.182.246.103',  # Example GitLab IP
]

ALLOWED_PORTS = [80, 443, 22, 5000, 4200, 8080]


def get_active_connections_windows():
    """Get active connections on Windows"""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting connections: {e}")
        return ""


def get_active_connections_linux():
    """Get active connections on Linux"""
    try:
        result = subprocess.run(
            ['netstat', '-tupln'],
            capture_output=True,
            text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting connections: {e}")
        return ""


def parse_connections(connections_output: str):
    """Parse network connections from netstat output"""
    connections = []
    lines = connections_output.split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        parts = line.split()
        if len(parts) < 4:
            continue
        
        try:
            # Parse local address:port and remote address:port
            local = parts[1] if len(parts) > 1 else ""
            remote = parts[2] if len(parts) > 2 else ""
            state = parts[3] if len(parts) > 3 else ""
            
            if 'ESTABLISHED' in state or 'LISTENING' in state:
                connections.append({
                    'local': local,
                    'remote': remote,
                    'state': state
                })
        except:
            pass
    
    return connections


def is_allowed_connection(remote_addr: str) -> bool:
    """Check if connection is allowed"""
    if not remote_addr or remote_addr in ['[::1]', '*', '0.0.0.0']:
        return True
    
    # Extract host
    host = remote_addr.split(':')[0]
    
    # Check if it's an allowed host
    for allowed in ALLOWED_HOSTS:
        if allowed in host or host in allowed:
            return True
    
    return False


def monitor_network():
    """Monitor network connections"""
    print("=" * 70)
    print("  Sakura Network Monitor")
    print("=" * 70)
    print("\nThis script monitors network connections to detect unauthorized communication.")
    print("Press Ctrl+C to stop monitoring.\n")
    
    if sys.platform.startswith('win'):
        get_connections = get_active_connections_windows
    else:
        get_connections = get_active_connections_linux
    
    try:
        while True:
            connections_output = get_connections()
            connections = parse_connections(connections_output)
            
            print(f"\n[{time.strftime('%H:%M:%S')}] Checking connections...")
            
            unauthorized = []
            authorized = []
            
            for conn in connections:
                remote = conn.get('remote', '')
                if remote and remote != '*':
                    if is_allowed_connection(remote):
                        authorized.append(conn)
                    else:
                        unauthorized.append(conn)
            
            if unauthorized:
                print(f"\n⚠️  UNAUTHORIZED CONNECTIONS DETECTED:")
                for conn in unauthorized:
                    print(f"   {conn}")
            else:
                print("  ✓ No unauthorized connections")
            
            # Count connections
            print(f"\n  Authorized connections: {len(authorized)}")
            if unauthorized:
                print(f"  ⚠️  Unauthorized connections: {len(unauthorized)}")
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
    except Exception as e:
        print(f"\nError during monitoring: {e}")


if __name__ == "__main__":
    monitor_network()









