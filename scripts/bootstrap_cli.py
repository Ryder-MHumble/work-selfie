#!/usr/bin/env python3
"""Bootstrap helper for WorkSelfie workplace data providers."""

import argparse
import json
import os
import shutil
import subprocess
from typing import Any, Callable, Dict, List

from workselfie_providers import ProviderSpec, get_provider, resolve_provider, supported_provider_names


RunCmd = Callable[[List[str]], subprocess.CompletedProcess]
HasCli = Callable[[str], bool]


def _env_binary_override(provider: ProviderSpec) -> str | None:
    key = f"WORKSELFIE_{provider.name.upper()}_BIN"
    return os.environ.get(key)


def _resolve_cli_path(provider: ProviderSpec) -> str:
    override = _env_binary_override(provider)
    if override:
        return override
    return shutil.which(provider.cli) or provider.cli


def _default_has_cli(cli: str) -> bool:
    return shutil.which(cli) is not None


def _default_run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _with_resolved_binary(provider: ProviderSpec, command: List[str]) -> List[str]:
    return [_resolve_cli_path(provider), *command[1:]]


def _success_message(provider: ProviderSpec, stdout: str) -> str:
    if provider.name == "dws":
        return "dws CLI is installed and auth status check succeeded."
    if provider.name == "lark":
        try:
            payload = json.loads(stdout)
            identities = payload.get("identities", {})
            bot_status = identities.get("bot", {}).get("status", "unknown")
            user_status = identities.get("user", {}).get("status", "unknown")
            return f"lark-cli is installed. bot={bot_status}, user={user_status}."
        except json.JSONDecodeError:
            return "lark-cli is installed and auth status check succeeded."
    return f"{provider.cli} status check succeeded."


def _dry_run_steps(provider: ProviderSpec) -> List[str]:
    if provider.name == "dws":
        return [
            "dws auth status --format json",
            "If auth is missing: dws auth login or dws auth login --device",
        ]
    return [
        "lark-cli config init --new",
        'lark-cli auth login --scope "<needed_scope>" --no-wait --json',
        "lark-cli auth qrcode <verification_url> --output /tmp/workselfie-lark-auth.png",
        "After user authorizes: lark-cli auth login --device-code <device_code>",
    ]


def bootstrap_provider(
    provider_name: str,
    dry_run: bool = False,
    has_cli: HasCli = _default_has_cli,
    run_cmd: RunCmd = _default_run_cmd,
) -> Dict[str, Any]:
    def has_cli_or_override(cli: str) -> bool:
        if cli == "dws" and os.environ.get("WORKSELFIE_DWS_BIN"):
            return True
        if cli == "lark-cli" and os.environ.get("WORKSELFIE_LARK_BIN"):
            return True
        return has_cli(cli)

    provider = resolve_provider(provider_name, has_cli=has_cli_or_override)
    cli_exists = has_cli(provider.cli) or bool(_env_binary_override(provider))

    if not cli_exists:
        return {
            "provider": provider.name,
            "display_name": provider.display_name,
            "ready": False,
            "status": "missing_cli",
            "message": provider.install_hint,
            "next_steps": [provider.install_hint],
        }

    if dry_run:
        return {
            "provider": provider.name,
            "display_name": provider.display_name,
            "ready": True,
            "status": "dry_run",
            "message": "CLI exists. Review the setup/auth plan before running it.",
            "next_steps": _dry_run_steps(provider),
        }

    status_cmd = _with_resolved_binary(provider, provider.status_command)
    completed = run_cmd(status_cmd)
    if completed.returncode == 0:
        return {
            "provider": provider.name,
            "display_name": provider.display_name,
            "ready": True,
            "status": "ok",
            "message": _success_message(provider, completed.stdout),
            "next_steps": [],
        }

    return {
        "provider": provider.name,
        "display_name": provider.display_name,
        "ready": False,
        "status": "auth_required",
        "message": (completed.stderr or completed.stdout or provider.auth_hint).strip(),
        "next_steps": [provider.auth_hint],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap WorkSelfie provider CLI")
    parser.add_argument("--provider", default="auto", choices=["auto", *supported_provider_names()])
    parser.add_argument("--dry-run", action="store_true", help="Show setup plan without running status checks")
    args = parser.parse_args()

    result = bootstrap_provider(args.provider, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
