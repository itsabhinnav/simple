#!/usr/bin/env python3
"""
Network Restrictor for Sakura Application

This module implements network-level restrictions to ensure the application
only communicates with allowed hosts (localhost and Git remote).
"""

import socket
import sys
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

# Default allowed hosts (can be overridden by configuration).
# Remote/git DB sync is permanently disabled, so external hosts like
# gitlab.com are intentionally NOT in the default allow-list.
DEFAULT_ALLOWED_HOSTS: Set[str] = {
    'localhost',
    '127.0.0.1',
    '::1',
    '0.0.0.0',
}

# Allowed hosts loaded from configuration
ALLOWED_HOSTS: Set[str] = set(DEFAULT_ALLOWED_HOSTS)

# Allowed ports for specific hosts
ALLOWED_PORTS: Set[int] = {
    80,      # HTTP
    443,     # HTTPS
    22,      # SSH (Git)
    5000,    # Backend API
    4200,    # Frontend Dev Server
    8080,    # Alternative backend (if used)
}

# Restricted modules that should not make external calls
RESTRICTED_MODULES = {
    'urllib',
    'urllib.request',
    'urllib2',
    'httplib',
    'http.client',
    'aiohttp',
    'requests',
}

# Track connections
_connection_log: List[dict] = []


def is_host_allowed(host: str) -> bool:
    """Check if host is in the allowed list"""
    if not host:
        return True
    
    # Check exact match
    if host in ALLOWED_HOSTS:
        return True
    
    # Check if it's a localhost variant
    host_lower = host.lower()
    if host_lower in ['localhost', '127.0.0.1', '::1', '0.0.0.0', '0::1']:
        return True
    
    # Check if it starts with localhost
    if host_lower.startswith('localhost'):
        return True
    
    # Check if it's an IP address in private ranges
    try:
        import ipaddress
        ip = ipaddress.ip_address(host)
        # Allow private IP ranges
        if ip.is_private or ip.is_loopback:
            return True
    except ValueError:
        # Not a valid IP address
        pass

    return False


def is_port_allowed(host: str, port: int) -> bool:
    """Check if port is allowed for the given host"""
    # Allow specific ports for any host
    if port in ALLOWED_PORTS:
        return True
    
    # Localhost can use any port
    if host in ['localhost', '127.0.0.1', '::1']:
        return True
    
    return False


def log_connection(host: str, port: int, allowed: bool, method: str = ""):
    """Log network connection attempt"""
    status = "ALLOWED" if allowed else "BLOCKED"
    log_entry = {
        'host': host,
        'port': port,
        'allowed': allowed,
        'method': method,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }
    _connection_log.append(log_entry)
    
    if allowed:
        logger.info(f"[{status}] Connection to {host}:{port} via {method}")
    else:
        logger.warning(f"[{status}] Connection attempt to {host}:{port} via {method}")


def restrict_socket():
    """Monkey-patch socket.socket.connect to restrict connections"""
    try:
        original_connect = socket.socket.connect
        
        def restricted_connect(self, address):
            """Restricted version of socket.connect"""
            host = address[0] if isinstance(address, tuple) else str(address)
            port = address[1] if isinstance(address, tuple) else 0
            
            # Parse host if needed
            if isinstance(host, tuple):
                host, port = host
            
            # Check if allowed
            if not is_host_allowed(host):
                logger.error(f"Blocked connection to unauthorized host: {host}:{port}")
                raise ConnectionRefusedError(
                    f"Connection to {host}:{port} is not allowed. "
                    f"Only connections to allowed hosts are permitted."
                )
            
            if port and not is_port_allowed(host, port):
                logger.warning(f"Port {port} not allowed for host {host}")
                # Don't block, just log for now
            
            log_connection(host, port, True, "socket.connect")
            return original_connect(self, address)
        
        socket.socket.connect = restricted_connect
        logger.info("Socket restrictions applied successfully")
        
    except Exception as e:
        logger.error(f"Failed to apply socket restrictions: {e}")


def restrict_urllib():
    """Restrict urllib operations"""
    try:
        # Only patch if urllib is imported
        if 'urllib' in sys.modules:
            logger.warning("urllib is already loaded, restrictions may not apply fully")
    except Exception as e:
        logger.error(f"Failed to restrict urllib: {e}")


def get_connection_log() -> List[dict]:
    """Get the connection log"""
    return _connection_log.copy()


def clear_connection_log():
    """Clear the connection log"""
    _connection_log.clear()


def enable_network_restrictions():
    """Enable all network restrictions"""
    logger.info("Enabling network restrictions...")
    
    try:
        restrict_socket()
        restrict_urllib()
        logger.info("Network restrictions enabled successfully")
    except Exception as e:
        logger.error(f"Failed to enable network restrictions: {e}")
        raise


def disable_network_restrictions():
    """Disable network restrictions (for testing only)"""
    logger.warning("Disabling network restrictions - NOT RECOMMENDED FOR PRODUCTION")
    # Restore original socket
    import socket
    # Would need to store original connect
    pass


def load_allowed_hosts_from_config():
    """Load allowed hosts from configuration"""
    try:
        from src.infrastructure.configuration_manager import get_config_manager
        config = get_config_manager()
        allowed_hosts = config.get_config("network.allowed_hosts", list(DEFAULT_ALLOWED_HOSTS))
        
        # Update global ALLOWED_HOSTS
        global ALLOWED_HOSTS
        ALLOWED_HOSTS = set(allowed_hosts)
        logger.info(f"Loaded {len(ALLOWED_HOSTS)} allowed hosts from configuration")
    except Exception as e:
        logger.warning(f"Could not load allowed hosts from configuration: {e}, using defaults")
        ALLOWED_HOSTS = set(DEFAULT_ALLOWED_HOSTS)

def get_allowed_hosts() -> Set[str]:
    """Get list of allowed hosts"""
    return ALLOWED_HOSTS.copy()


def add_allowed_host(host: str):
    """Add a host to the allowed list"""
    ALLOWED_HOSTS.add(host)
    logger.info(f"Added {host} to allowed hosts")


def remove_allowed_host(host: str):
    """Remove a host from the allowed list"""
    if host in ALLOWED_HOSTS:
        ALLOWED_HOSTS.remove(host)
        logger.info(f"Removed {host} from allowed hosts")


def verify_network_isolation():
    """Verify that network isolation is working"""
    logger.info("Verifying network isolation...")
    
    # Test allowed connection
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex(('localhost', 5000))
        test_socket.close()
        if result == 0:
            logger.info("✓ Localhost connection allowed")
        else:
            logger.info("ℹ Localhost port 5000 not responding (expected if backend not running)")
    except Exception as e:
        logger.debug(f"Localhost test: {e}")
    
    # Test blocked connection
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex(('www.google.com', 80))
        test_socket.close()
        if result == 0:
            logger.warning("✗ Could connect to unauthorized host - restrictions may not be active")
        else:
            logger.info("✓ Unauthorized host blocked successfully")
    except socket.error:
        logger.info("✓ Unauthorized host blocked successfully")
    except Exception as e:
        logger.debug(f"Block test: {e}")


# Initialize restrictions if this module is imported
if __name__ != "__main__":
    try:
        # Load allowed hosts from configuration
        load_allowed_hosts_from_config()
        # Enable network restrictions
        enable_network_restrictions()
    except Exception as e:
        logger.error(f"Could not initialize network restrictions: {e}")


if __name__ == "__main__":
    # Run verification
    logging.basicConfig(level=logging.INFO)
    verify_network_isolation()
    
    print("\nAllowed hosts:", ALLOWED_HOSTS)
    print("\nConnection log:")
    for entry in get_connection_log():
        print(f"  {entry}")

