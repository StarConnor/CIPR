"""
VS Code Extension Automation Server

A FastAPI server for automating VS Code extensions using pywinauto.
"""
import logging
import argparse
from pathlib import Path
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import config_loader, ServerConfig

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path("/app/.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logging.info(f"Loaded environment variables from {env_path}")
    else:
        logging.warning(f".env file not found at {env_path}")
except ImportError:
    logging.warning("python-dotenv not installed, .env file will not be loaded")

# Setup logging with configurable level from environment
server_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
try:
    log_level = getattr(logging, server_log_level, logging.INFO)
except (AttributeError, TypeError):
    log_level = logging.INFO
    server_log_level = "INFO"

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Server logging level set to: {server_log_level}")


def create_app(server_config: ServerConfig = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="VS Code Extension Automation Server",
        description="API for automating VS Code extensions using pywinauto",
        version="1.0.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routes
    app.include_router(router, prefix="/api/v1")
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize on startup."""
        logger.info("Starting VS Code Automation Server...")
        
        # Load server config if not provided
        nonlocal server_config
        if server_config is None:
            server_config = config_loader.load_server_config()
        
        # Initialize IDE controller if available (optional for CLI-only mode)
        try:
            from .core.controller import init_controller
            init_controller(
                process_name=server_config.vscode_process_name,
                window_title_regex=server_config.vscode_window_title,
                timeout=server_config.default_timeout,
                retry_interval=server_config.retry_interval,
            )
            logger.info(f"IDE controller initialized with process_name={server_config.vscode_process_name}")
        except ImportError:
            logger.info("IDE controller not available - running in CLI-only mode")
        except Exception as e:
            logger.warning(f"Failed to initialize IDE controller: {e}")
        
        # Load all extension configs
        config_loader.extensions_dir = Path(server_config.extensions_dir)
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down VS Code Automation Server...")
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "VS Code Extension Automation Server",
            "version": "1.0.0",
            "docs": "/docs",
        }
    
    return app


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="VS Code Extension Automation Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--config", default="automation_server\\server_config.yaml", help="Path to server config")
    parser.add_argument("--extensions-dir", default="extensions", help="Path to extensions directory")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    # Use environment variable as default, command-line can override
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Logging level")
    
    args = parser.parse_args()
    
    # Set log level (respects both env var and command-line arg)
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Load or create server config
    config_path = Path(args.config).absolute()
    if config_path.exists():
        server_config = config_loader.load_server_config(str(config_path))
    else:
        print(f"Config file not found at {config_path}, using default settings")
        server_config = ServerConfig(
            host=args.host,
            port=args.port,
            extensions_dir=args.extensions_dir,
            log_level=args.log_level,
        )
    
    # Create app
    app = create_app(server_config)
    
    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


# For running with `python -m automation_server`
if __name__ == "__main__":
    main()
