import tomli
from pathlib import Path
from typing import Any
from pegasus.config.config import Config
from platformdirs import user_config_dir
from pegasus.utils.errors import ConfigError
from pegasus.utils.logger import logger

_CONFIG_FILE_NAME = "config.json"

def get_config_dir() -> Path:
    return Path(user_config_dir("pegasus", appauthor=False))

def get_system_config_path() -> Path:
    return get_config_dir() / _CONFIG_FILE_NAME

def _parse_toml(path: Path):
    try:
        with open(path, "rb") as f:
            return tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ConfigError(
            message=f"Invalid TOML file in {path}: {e}",
            config_file=path,
            cause=e
        )
    except (OSError, IOError) as e:
        raise ConfigError(
            message=f"Failed to read TOML file in {path}: {e}",
            config_file=path,
            cause=e
        )

def _get_project_config(cwd: Path) -> Path:
    current = cwd.resolve()
    agent_dir = current / ".pegasus"
    if agent_dir.is_dir():
        config_path = agent_dir / "config.toml"
        if config_path.is_file():
            return config_path
    return None


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()
    system_path = get_system_config_path()
    config_dict: dict[str, Any] = {}
    if system_path.is_file():
        try:
           config_dict = _parse_toml(system_path)
        except ConfigError as e:
            logger.warning(f"Failed to load system config: {e}")
    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_dict = _parse_toml(project_path)
            config_dict = _merge_dicts(config_dict, project_dict)
        except ConfigError as e:
            logger.warning(f"Failed to load project config: {e}")

    if "cwd" not in config_dict:
        config_dict["cwd"] = cwd

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ConfigError(
            message=f"Invalid config: {e}",
            config_file=system_path,
            cause=e
        ) from e
    return config