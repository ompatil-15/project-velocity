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


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging():
    """Configure all loggers with standard format."""
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root.handlers = [handler]
    
    # Configure uvicorn loggers to use same format
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False
    
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

