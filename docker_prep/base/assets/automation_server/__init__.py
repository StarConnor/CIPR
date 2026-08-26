"""
VS Code Extension Automation Server

A config-driven server for automating VS Code extensions using pywinauto.
"""
from .server import create_app, main
from .config import ExtensionConfig, ServerConfig, config_loader
from .core import ActionExecutor

__version__ = "1.0.0"

__all__ = [
    "create_app",
    "main",
    "ExtensionConfig",
    "ServerConfig",
    "config_loader",
    "ActionExecutor",
]
