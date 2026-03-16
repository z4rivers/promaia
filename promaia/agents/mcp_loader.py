"""
MCP server configuration for Claude Agent SDK.
"""
import os
import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_env_value(value: Any) -> Any:
    """
    Resolve env var placeholders like "${VAR}".

    Leaves non-strings and non-placeholder strings unchanged.
    """
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        var = value[2:-1]
        return os.getenv(var, "")
    return value


def _looks_like_relative_path(value: str) -> bool:
    if value in {".", ".."}:
        return True
    return value.startswith("./") or value.startswith("../")


def _resolve_arg_paths(args: list[str], base_dir: Path) -> list[str]:
    """
    Best-effort conversion of path-like args to absolute paths using base_dir.

    This is important when the scheduler runs with a different CWD: many MCP
    servers are configured with args like "." or "data/foo.db".
    """
    resolved: list[str] = []
    for arg in args:
        # Leave obviously non-path args as-is
        if not isinstance(arg, str) or not arg:
            resolved.append(arg)
            continue

        if Path(arg).is_absolute():
            resolved.append(arg)
            continue

        candidate: Path | None = None

        if _looks_like_relative_path(arg):
            candidate = (base_dir / arg).resolve()
        else:
            # Heuristic: if it contains a path separator OR looks like a file,
            # and it exists relative to base_dir, treat it as a path.
            if ("/" in arg or arg.endswith((".db", ".sqlite", ".json", ".yaml", ".yml", ".md", ".txt"))):
                maybe = (base_dir / arg).resolve()
                if maybe.exists():
                    candidate = maybe
            else:
                # Special-case common conventions used in our config
                if arg.startswith("data/") or arg.startswith("data\\"):
                    maybe = (base_dir / arg).resolve()
                    if maybe.exists():
                        candidate = maybe

        resolved.append(str(candidate) if candidate is not None else arg)
    return resolved


def _find_mcp_servers_json() -> Path | None:
    """
    Locate mcp_servers.json in a way that works for cron/daemons.

    Search order:
    - PROMAIA_MCP_SERVERS_PATH (explicit override)
    - current working directory
    - directory containing promaia.config.json (if found)
    - repository/package ancestors (walk up from this file)
    - ~/.promaia/mcp_servers.json
    """
    override = os.getenv("PROMAIA_MCP_SERVERS_PATH")
    if override:
        p = Path(override).expanduser()
        if p.exists():
            return p
        logger.warning(f"PROMAIA_MCP_SERVERS_PATH set but not found: {p}")

    # CWD first (legacy behavior)
    cwd_candidate = Path.cwd() / "mcp_servers.json"
    if cwd_candidate.exists():
        return cwd_candidate

    # Next: alongside promaia.config.json (often stored in ~/.promaia)
    try:
        from promaia.agents.agent_config import get_config_file_path

        config_path = get_config_file_path()
        candidate = config_path.parent / "mcp_servers.json"
        if candidate.exists():
            return candidate
    except Exception:
        # Avoid import-time failures from blocking tool loading
        pass

    # Walk up from this module to find repo root
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "mcp_servers.json"
        if candidate.exists():
            return candidate
        # Stop at project markers to avoid scanning too far
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            candidate = parent / "mcp_servers.json"
            if candidate.exists():
                return candidate
            # Even if not found, don't continue past repo root marker
            break

    # Home fallback
    home_candidate = Path.home() / ".promaia" / "mcp_servers.json"
    if home_candidate.exists():
        return home_candidate

    return None


def load_mcp_servers_for_agent(agent_config) -> Dict[str, Any]:
    """
    Load MCP servers from agent config for SDK.

    Args:
        agent_config: AgentConfig with mcp_tools field

    Returns:
        Dict in SDK format: {server_name: {type, command, args, env}}
    """
    if not agent_config.mcp_tools:
        return {}

    mcp_servers_path = _find_mcp_servers_json()
    if not mcp_servers_path:
        logger.warning("mcp_servers.json not found, MCP tools will not be available")
        return {}

    try:
        # Load from global mcp_servers.json
        with open(mcp_servers_path, encoding='utf-8') as f:
            all_servers = json.load(f).get('servers', {})

        base_dir = mcp_servers_path.parent.resolve()

        # Filter to enabled tools only
        enabled_servers = {}
        for tool_name in agent_config.mcp_tools:
            if tool_name in all_servers:
                server_config = all_servers[tool_name].copy()

                # Convert to SDK format
                raw_command = server_config["command"]
                command = raw_command[0] if isinstance(raw_command, list) else raw_command
                base_args = raw_command[1:] if isinstance(raw_command, list) else []

                extra_args = server_config.get("args") or []

                # Resolve any relative args against where mcp_servers.json lives,
                # not the current process CWD.
                combined_args = _resolve_arg_paths([*base_args, *extra_args], base_dir=base_dir)

                # Note: Claude CLI expects just command/args/env, not "type" field
                sdk_config = {
                    "command": command,
                    "args": combined_args
                }

                # Add env if present (SDK expects dict of string:string)
                if "env" in server_config:
                    sdk_config["env"] = {k: _resolve_env_value(v) for k, v in server_config["env"].items()}

                enabled_servers[tool_name] = sdk_config
                logger.debug(f"Enabled MCP server: {tool_name} (config: {mcp_servers_path})")
            else:
                logger.warning(f"MCP server '{tool_name}' not found in mcp_servers.json")

        return enabled_servers

    except Exception as e:
        logger.error(f"Error loading MCP servers: {e}")
        return {}
