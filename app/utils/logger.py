"""
Centralized logging configuration for Project Velocity.

Usage:
    from app.utils.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing started")
    logger.debug("Variable value: %s", value)
    logger.error("Operation failed: %s", error)
"""

import logging
import sys
import os
from datetime import datetime


# Log format configuration
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Environment-based log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging():
    """Configure root logger with standard format."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module.
    
    Args:
        name: Module name, typically __name__
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Initialize logging on import
setup_logging()


# Convenience loggers for common components
api_logger = get_logger("api")
workflow_logger = get_logger("workflow")
node_logger = get_logger("node")
tool_logger = get_logger("tool")

