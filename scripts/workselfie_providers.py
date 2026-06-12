#!/usr/bin/env python3
"""Provider registry for workplace data CLIs used by WorkSelfie."""

from dataclasses import dataclass
import shutil
from typing import Callable, Dict, List


HasCli = Callable[[str], bool]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    cli: str
    display_name: str
    data_sources: List[str]
    status_command: List[str]
    auth_hint: str
    install_hint: str


PROVIDERS: Dict[str, ProviderSpec] = {
    "dws": ProviderSpec(
        name="dws",
        cli="dws",
        display_name="DingTalk / DWS",
        data_sources=["chat", "minutes", "doc", "aitable"],
        status_command=["dws", "auth", "status", "--format", "json"],
        auth_hint=(
            "Run `dws auth login` or `dws auth login --device`, then re-run "
            "`python3 scripts/bootstrap_cli.py --provider dws`."
        ),
        install_hint=(
            "`dws` was not found in PATH. Ask the agent to install the official dws CLI "
            "for your environment, or set WORKSELFIE_DWS_BIN=/absolute/path/to/dws."
        ),
    ),
    "lark": ProviderSpec(
        name="lark",
        cli="lark-cli",
        display_name="Lark / Feishu",
        data_sources=["chat", "minutes", "doc", "base"],
        status_command=["lark-cli", "auth", "status"],
        auth_hint=(
            "First run `lark-cli config init --new` if app config is missing. "
            "For user auth, use split-flow: "
            "`lark-cli auth login --scope \"<scope>\" --no-wait --json`, "
            "render the verification URL with `lark-cli auth qrcode`, then finish "
            "later with `lark-cli auth login --device-code <device_code>`."
        ),
        install_hint=(
            "`lark-cli` was not found in PATH. Ask the agent to install the official "
            "lark-cli for your environment, or set WORKSELFIE_LARK_BIN=/absolute/path/to/lark-cli."
        ),
    ),
}


def _default_has_cli(cli: str) -> bool:
    return shutil.which(cli) is not None


def supported_provider_names() -> List[str]:
    return list(PROVIDERS.keys())


def get_provider(name: str) -> ProviderSpec:
    normalized = name.lower().strip()
    if normalized not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {name}. Expected one of: {', '.join(PROVIDERS)}")
    return PROVIDERS[normalized]


def resolve_provider(name: str = "auto", has_cli: HasCli = _default_has_cli) -> ProviderSpec:
    normalized = name.lower().strip()
    if normalized != "auto":
        return get_provider(normalized)

    for candidate in ("dws", "lark"):
        spec = PROVIDERS[candidate]
        if has_cli(spec.cli):
            return spec

    # Prefer dws as the historical default when neither CLI is installed.
    return PROVIDERS["dws"]
