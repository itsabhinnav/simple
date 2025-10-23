"""
Logging Configuration

This module provides centralized logging configuration for the application,
following the Single Responsibility Principle (SRP) of SOLID.
"""

import logging
import logging.handlers
import sys
from typing import Optional
from pathlib import Path

from config.settings import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging() -> logging.Logger:
    """
    Set up application logging configuration.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("artifactory_app")
    logger.setLevel(getattr(logging, settings.logging.level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if settings.logging.enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.logging.level.upper()))
        
        # Use colored formatter for console
        console_formatter = ColoredFormatter(settings.logging.format)
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(console_handler)
    
    # File handler
    if settings.logging.file_path:
        file_path = Path(settings.logging.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=settings.logging.max_file_size,
            backupCount=settings.logging.backup_count
        )
        file_handler.setLevel(getattr(logging, settings.logging.level.upper()))
        
        # Use standard formatter for file
        file_formatter = logging.Formatter(settings.logging.format)
        file_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(f"artifactory_app.{name}")


# Set up logging on module import
app_logger = setup_logging()
