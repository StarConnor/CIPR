"""YAML config loader for extensions."""
import os
from pathlib import Path
from typing import Dict, Optional
import yaml

from .schema import ExtensionConfig, ServerConfig


class ConfigLoader:
    """Loads and manages extension configurations."""
    
    def __init__(self, extensions_dir: str = "extensions"):
        self.extensions_dir = Path(extensions_dir)
        self._extensions: Dict[str, ExtensionConfig] = {}
        self._server_config: Optional[ServerConfig] = None
    
    def load_server_config(self, config_path: str = "server_config.yaml") -> ServerConfig:
        """Load server configuration from YAML file."""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._server_config = ServerConfig(**data)
        else:
            self._server_config = ServerConfig()
        return self._server_config
    
    def load_extension(self, config_path: Path) -> ExtensionConfig:
        """Load a single extension configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = ExtensionConfig(**data)
        self._extensions[config.name] = config
        return config
    
    def load_all_extensions(self) -> Dict[str, ExtensionConfig]:
        """Load all extension configurations from the extensions directory."""
        if not self.extensions_dir.exists():
            self.extensions_dir.mkdir(parents=True, exist_ok=True)
            return {}
        
        for config_file in self.extensions_dir.glob("*.yaml"):
            try:
                self.load_extension(config_file)
            except Exception as e:
                print(f"Error loading {config_file}: {e}")
        
        for config_file in self.extensions_dir.glob("*.yml"):
            try:
                self.load_extension(config_file)
            except Exception as e:
                print(f"Error loading {config_file}: {e}")
        
        return self._extensions
    
    def get_extension(self, name: str) -> Optional[ExtensionConfig]:
        """Get a loaded extension configuration by name."""
        return self._extensions.get(name)
    
    def list_extensions(self) -> Dict[str, ExtensionConfig]:
        """List all loaded extensions."""
        return self._extensions.copy()
    
    def reload_extension(self, name: str) -> Optional[ExtensionConfig]:
        """Reload a specific extension configuration."""
        for config_file in self.extensions_dir.glob(f"{name}.yaml"):
            return self.load_extension(config_file)
        for config_file in self.extensions_dir.glob(f"{name}.yml"):
            return self.load_extension(config_file)
        return None
    
    def register_extension(self, config: ExtensionConfig) -> ExtensionConfig:
        """Register an extension configuration dynamically (not from file)."""
        self._extensions[config.name] = config
        return config
    
    def register_extension_from_yaml(self, yaml_content: str) -> ExtensionConfig:
        """Register an extension from YAML string."""
        data = yaml.safe_load(yaml_content)
        config = ExtensionConfig(**data)
        self._extensions[config.name] = config
        return config
    
    def unregister_extension(self, name: str) -> bool:
        """Unregister/remove an extension configuration."""
        if name in self._extensions:
            del self._extensions[name]
            return True
        return False
    
    def extension_exists(self, name: str) -> bool:
        """Check if an extension is registered."""
        return name in self._extensions


# Global config loader instance
config_loader = ConfigLoader()
