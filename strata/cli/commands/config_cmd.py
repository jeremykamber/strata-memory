"""Show or modify Strata configuration."""

from __future__ import annotations

import sys

from strata.cli._json import json_print, json_error, is_json_mode
from strata.cli._config import (
    load_config,
    save_strata_config,
    config_to_dict,
    get_config_value,
    set_config_value,
    parse_config_value,
    read_llm_config,
    write_llm_config,
)

name = "config"


def run(args: list[str]) -> None:
    """Handle the ``config`` command: show or modify configuration.

    Subcommands:
        ``strata config``              Show all config values.
        ``strata config get <key>``    Get a specific value.
        ``strata config set <key> <v>`` Set a config value.
    """
    config = load_config()

    # No args — show all config
    if not args:
        if is_json_mode():
            json_print("config", config_to_dict(config))
            return
        print("strata Configuration")
        print(f"{'=' * 40}")
        print(f"  base_dir:           {config.base_dir.resolve()}")
        print(f"  active_dir:         {config.active_dir}")
        print(f"  cooled_dir:         {config.cooled_dir}")
        print(f"  qmd_enabled:        {config.qmd_enabled}")
        print(f"  stratum_3_archive:     {config.stratum_3_archive}")
        print(f"  stratum_3_shadow_db:   {config.stratum_3_shadow_db}")
        print("")
        print("  Decay thresholds:")
        for pattern, days in sorted(config.decay_thresholds.items()):
            print(f"    /{pattern}:  {days} days")
        print("")
        print(
            f"  LRU eviction:       {config.lru_days} days, \u2264{config.lru_min_access_count} access(es)"
        )
        print(f"  QMD enabled:        {config.qmd_enabled}")
        print(f"  File patterns:      {', '.join(config.active_file_patterns)}")
        return

    # config get <key>
    if args[0] == "get" and len(args) >= 2:
        key = args[1]
        # Route llm.* keys to pi-config.json
        if key == "llm" or key.startswith("llm."):
            llm_cfg = read_llm_config(config)
            if llm_cfg is None:
                print("LLM not configured (no pi-config.json)", file=sys.stderr)
                sys.exit(1)
            if key == "llm":
                if is_json_mode():
                    json_print("config", {"key": key, "value": llm_cfg})
                    return
                for k, v in llm_cfg.items():
                    print(f"  llm.{k} = {v!r}")
                return
            # key is llm.<subkey>
            sub = key.split(".", 1)[1]
            if sub not in llm_cfg:
                print(f"Unknown config key: {key}", file=sys.stderr)
                sys.exit(1)
            if is_json_mode():
                json_print("config", {"key": key, "value": llm_cfg[sub]})
                return
            print(llm_cfg[sub])
            return
        try:
            value = get_config_value(config, key)
        except (KeyError, AttributeError):
            if is_json_mode():
                json_error("config", f"Unknown config key: {key}")
            print(f"Unknown config key: {key}", file=sys.stderr)
            sys.exit(1)
        if is_json_mode():
            json_print("config", {"key": key, "value": value})
            return
        print(value)
        return

    # config set <key> <value>
    if args[0] == "set" and len(args) >= 2:
        key = args[1]
        # If setting llm.apiKey with no value, prompt securely
        if len(args) == 2 and key.endswith("apiKey"):
            import getpass

            raw_value = getpass.getpass("Enter API key: ")
            if not raw_value:
                print("No key provided, aborting.", file=sys.stderr)
                sys.exit(1)
        elif len(args) < 3:
            if is_json_mode():
                json_error("config", "Usage: strata config set <key> <value>")
            print("Usage: strata config set <key> <value>", file=sys.stderr)
            sys.exit(1)
        else:
            raw_value = " ".join(args[2:])
        value = parse_config_value(raw_value)
        # Route llm.* keys to pi-config.json
        if key == "llm" or key.startswith("llm."):
            llm_cfg = read_llm_config(config) or {}
            if key == "llm":
                if not isinstance(value, dict):
                    print("llm value must be a JSON object", file=sys.stderr)
                    sys.exit(1)
                llm_cfg.clear()
                llm_cfg.update(value)
            else:
                sub = key.split(".", 1)[1]
                llm_cfg[sub] = value
            write_llm_config(config, llm_cfg)
            if is_json_mode():
                json_print("config", {"key": key, "value": value, "set": True})
                return
            print(
                f"Set llm.{key.split('.', 1)[1] if '.' in key else ''} = {value!r}"
                if "." in key
                else "Set llm config"
            )
            return
        # Validate top-level key
        top = key.split(".")[0]
        if not hasattr(config, top):
            if is_json_mode():
                json_error("config", f"Unknown config key: {key}")
            print(f"Unknown config key: {key}", file=sys.stderr)
            sys.exit(1)
        try:
            set_config_value(config, key, value)
        except (KeyError, AttributeError):
            if is_json_mode():
                json_error("config", f"Cannot set config key: {key}")
            print(f"Cannot set config key: {key}", file=sys.stderr)
            sys.exit(1)
        save_strata_config(config)
        if is_json_mode():
            json_print("config", {"key": key, "value": value, "set": True})
            return
        print(f"Set config.{key} = {value!r}")
        return

    # Unknown subcommand
    if is_json_mode():
        json_error("config", "Usage: strata config [get <key> | set <key> <value>]")
    print("Usage: strata config [get <key> | set <key> <value>]", file=sys.stderr)
    sys.exit(1)
