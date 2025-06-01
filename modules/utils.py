from typing import Dict, Any, Optional
import yaml
import json


def load_yaml_config(config_path: str, key: str = "") -> Dict[str, Any]:
    """
    Load bot token from YAML configuration file.
    Args:
        key (str): Optional key to retrieve specific configuration value.
                    If empty, returns the entire configuration.
        config_path (str): Path to the configuration file containing bot token.
    Returns:
        config (dict): dictionary containing the configuration values.

    Raises:
        FileNotFoundError: If config file doesn't exist
        KeyError: If bot_token is not found in config
    """
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

            if key:
                return config.get(key, {})
            else:
                return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except KeyError:
        raise KeyError(f"Key '{key}' not found in configuration file")


def load_json_config(config_path: str, key: str = "") -> Dict[str, Any]:
    """Load JSON config files
    Args:
        config_path (str): Path to the configuration file.
        key (str): Optional key to retrieve specific configuration value.
                   If empty, returns the entire configuration.
    Returns:
        config (dict): Dictionary containing the configuration values.
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is not valid JSON
        KeyError: If key is not found in config
    """
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        if key:
            return config.get(key, {})
        else:
            return config.get(key, {})
    except FileNotFoundError:
        print(f"Configuration file {config_path} not found")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        return {}
    except KeyError:
        print(f"Key '{key}' not found in configuration file")
        return {}
