import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from sports_edge_scanner.core.execution import ExecutionOrder


REDACTED = "<redacted>"


@dataclass(frozen=True, repr=False)
class PolymarketCredentials:
    private_key: str
    api_key: str
    api_secret: str
    api_passphrase: str
    funder: str
    signature_type: int = 0

    def __post_init__(self) -> None:
        missing = [
            name
            for name, value in [
                ("private_key", self.private_key),
                ("api_key", self.api_key),
                ("api_secret", self.api_secret),
                ("api_passphrase", self.api_passphrase),
                ("funder", self.funder),
            ]
            if not value
        ]
        if missing:
            raise ValueError(f"missing credential values: {', '.join(missing)}")

    def __repr__(self) -> str:
        return (
            "PolymarketCredentials("
            "redacted_credentials=True, "
            f"funder='{self.funder}', signature_type={self.signature_type})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "private_key": REDACTED,
            "api_key": REDACTED,
            "api_secret": REDACTED,
            "api_passphrase": REDACTED,
            "funder": self.funder,
            "signature_type": self.signature_type,
        }


class CredentialProvider(Protocol):
    def load(self) -> PolymarketCredentials:
        ...


@dataclass(frozen=True)
class PolymarketAuthConfig:
    enabled: bool = False
    host: str = "https://clob.polymarket.com"
    chain_id: int = 137
    signature_type: int = 0
    funder_env: str = "POLYMARKET_FUNDER"
    private_key_env: str = "POLYMARKET_PRIVATE_KEY"
    api_key_env: str = "POLYMARKET_API_KEY"
    api_secret_env: str = "POLYMARKET_API_SECRET"
    api_passphrase_env: str = "POLYMARKET_API_PASSPHRASE"
    require_geoblock_check: bool = True
    allow_live_writes: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnvironmentPolymarketCredentialProvider:
    def __init__(self, config: PolymarketAuthConfig | None = None) -> None:
        self.config = config or PolymarketAuthConfig()

    def load(self) -> PolymarketCredentials:
        values = {
            "private_key": os.getenv(self.config.private_key_env, ""),
            "api_key": os.getenv(self.config.api_key_env, ""),
            "api_secret": os.getenv(self.config.api_secret_env, ""),
            "api_passphrase": os.getenv(self.config.api_passphrase_env, ""),
            "funder": os.getenv(self.config.funder_env, ""),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(
                "missing credential environment variables: " + ", ".join(missing)
            )
        return PolymarketCredentials(
            **values,
            signature_type=int(
                os.getenv("POLYMARKET_SIGNATURE_TYPE", self.config.signature_type)
            ),
        )


def write_polymarket_auth_config_template(path: Path, force: bool = False) -> Path:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(PolymarketAuthConfig().to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_polymarket_auth_config(path: Path) -> PolymarketAuthConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PolymarketAuthConfig(**payload)


@dataclass(frozen=True)
class GeoblockStatus:
    blocked: bool
    country: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PolymarketGeoblockClient:
    def __init__(self, url: str = "https://polymarket.com/api/geoblock") -> None:
        self.url = url

    def check(self) -> GeoblockStatus:
        request = urllib.request.Request(
            self.url,
            headers={"User-Agent": "sports-edge-scanner/0.1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("geoblock response must be an object")
        return GeoblockStatus(
            blocked=bool(payload.get("blocked")),
            country=str(payload.get("country") or ""),
            raw=payload,
        )


def map_execution_order_to_polymarket_args(order: ExecutionOrder) -> dict[str, Any]:
    if order.order_type != "LIMIT":
        raise ValueError("unsupported order type")
    if order.side not in {"BUY", "SELL"}:
        raise ValueError("unsupported order side")
    size = order.notional / order.limit_price
    return {
        "token_id": order.token_id,
        "side": order.side,
        "price": order.limit_price,
        "size": size,
        "time_in_force": order.time_in_force,
        "client_order_id": order.client_order_id,
    }
