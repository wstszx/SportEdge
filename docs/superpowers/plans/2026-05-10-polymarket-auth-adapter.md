# Polymarket Authenticated Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a readiness-first Polymarket authenticated adapter boundary that keeps credentials redacted, geoblock checks explicit, SDK calls injectable, and real writes disabled by default.

**Architecture:** Create a focused `sports_edge_scanner.connectors.polymarket_auth` module for credential providers, non-secret config, geoblock checks, order mapping, and an SDK-backed `ExecutionClient` adapter. Add readiness-only CLI commands under `polymarket-auth`; do not add a command that places real orders.

**Tech Stack:** Python 3.10+, dataclasses, standard-library urllib/json/os, existing `ExecutionClient` models, pytest with fake SDK clients.

---

## File Structure

- Create `sports_edge_scanner/connectors/polymarket_auth.py`: credential redaction, environment credential provider, config helpers, geoblock client, order mapper, and authenticated adapter.
- Modify `sports_edge_scanner/cli.py`: add `polymarket-auth init-config`, `polymarket-auth check`, and `polymarket-auth geoblock`.
- Modify `README.md`: document readiness-only authenticated adapter checks and safety boundaries.
- Create `tests/test_polymarket_auth_credentials.py`: credential/config redaction tests.
- Create `tests/test_polymarket_auth_adapter.py`: geoblock, order mapping, fake SDK adapter tests.
- Create `tests/test_polymarket_auth_cli.py`: readiness CLI tests and no-real-order parser checks.

## Task 1: Credential Redaction And Config Template

**Files:**
- Create: `sports_edge_scanner/connectors/polymarket_auth.py`
- Create: `tests/test_polymarket_auth_credentials.py`

- [ ] **Step 1: Write failing credential tests**

Create `tests/test_polymarket_auth_credentials.py`:

```python
import json

import pytest

from sports_edge_scanner.connectors.polymarket_auth import (
    EnvironmentPolymarketCredentialProvider,
    PolymarketAuthConfig,
    PolymarketCredentials,
    load_polymarket_auth_config,
    write_polymarket_auth_config_template,
)


def test_credentials_redact_secret_values():
    credentials = PolymarketCredentials(
        private_key="secret-private",
        api_key="secret-key",
        api_secret="secret-api-secret",
        api_passphrase="secret-passphrase",
        funder="0xfunder",
        signature_type=0,
    )

    payload = credentials.to_dict()

    assert payload == {
        "private_key": "<redacted>",
        "api_key": "<redacted>",
        "api_secret": "<redacted>",
        "api_passphrase": "<redacted>",
        "funder": "0xfunder",
        "signature_type": 0,
    }
    assert "secret" not in repr(credentials)


def test_environment_provider_loads_required_values(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "private")
    monkeypatch.setenv("POLYMARKET_API_KEY", "key")
    monkeypatch.setenv("POLYMARKET_API_SECRET", "secret")
    monkeypatch.setenv("POLYMARKET_API_PASSPHRASE", "pass")
    monkeypatch.setenv("POLYMARKET_FUNDER", "0xfunder")
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "1")

    credentials = EnvironmentPolymarketCredentialProvider().load()

    assert credentials.funder == "0xfunder"
    assert credentials.signature_type == 1
    assert credentials.private_key == "private"


def test_environment_provider_rejects_missing_values(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)

    with pytest.raises(ValueError, match="missing credential environment variables"):
        EnvironmentPolymarketCredentialProvider().load()


def test_auth_config_template_contains_env_names_not_secrets(tmp_path):
    path = tmp_path / "polymarket_auth_config.json"

    write_polymarket_auth_config_template(path)
    loaded = load_polymarket_auth_config(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert loaded.enabled is False
    assert loaded.allow_live_writes is False
    assert payload["private_key_env"] == "POLYMARKET_PRIVATE_KEY"
    assert "secret-private" not in path.read_text(encoding="utf-8")
    assert "api_secret" in payload
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_auth_credentials.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'sports_edge_scanner.connectors.polymarket_auth'`.

- [ ] **Step 3: Implement credential/config module**

Create `sports_edge_scanner/connectors/polymarket_auth.py`:

```python
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


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
            f"private_key='{REDACTED}', api_key='{REDACTED}', "
            f"api_secret='{REDACTED}', api_passphrase='{REDACTED}', "
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
            signature_type=int(os.getenv("POLYMARKET_SIGNATURE_TYPE", self.config.signature_type)),
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
```

- [ ] **Step 4: Run credential tests**

Run: `python -m pytest tests/test_polymarket_auth_credentials.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/connectors/polymarket_auth.py tests/test_polymarket_auth_credentials.py
git commit -m "feat: add polymarket auth credentials"
```

## Task 2: Geoblock Client And Order Mapper

**Files:**
- Modify: `sports_edge_scanner/connectors/polymarket_auth.py`
- Create: `tests/test_polymarket_auth_adapter.py`

- [ ] **Step 1: Write failing geoblock and mapper tests**

Create `tests/test_polymarket_auth_adapter.py`:

```python
import io
import json

import pytest

from sports_edge_scanner.connectors.polymarket_auth import (
    GeoblockStatus,
    PolymarketGeoblockClient,
    map_execution_order_to_polymarket_args,
)
from sports_edge_scanner.core.execution import ExecutionOrder


def order(**overrides):
    values = {
        "client_order_id": "client-1",
        "market_id": "m1",
        "market_slug": "market-1",
        "outcome_name": "Team A",
        "token_id": "token-a",
        "side": "BUY",
        "order_type": "LIMIT",
        "limit_price": 0.5,
        "notional": 10.0,
        "time_in_force": "IOC",
        "source_signal_id": "signal-1",
        "created_at": "2026-05-10T00:00:00+00:00",
        "venue": "polymarket",
    }
    values.update(overrides)
    return ExecutionOrder(**values)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_geoblock_client_normalizes_status(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"blocked": True, "country": "US"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    status = PolymarketGeoblockClient().check()

    assert status == GeoblockStatus(blocked=True, country="US", raw={"blocked": True, "country": "US"})


def test_order_mapper_converts_valid_order_to_sdk_args():
    args = map_execution_order_to_polymarket_args(order())

    assert args == {
        "token_id": "token-a",
        "side": "BUY",
        "price": 0.5,
        "size": 20.0,
        "time_in_force": "IOC",
        "client_order_id": "client-1",
    }


def test_order_mapper_rejects_unsupported_order_type():
    with pytest.raises(ValueError, match="unsupported order type"):
        map_execution_order_to_polymarket_args(order(order_type="LIMIT_MAKER"))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_auth_adapter.py -q`

Expected: FAIL because geoblock and mapper do not exist.

- [ ] **Step 3: Implement geoblock client and mapper**

Append to `sports_edge_scanner/connectors/polymarket_auth.py`:

```python
import urllib.request

from sports_edge_scanner.core.execution import ExecutionOrder


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
```

- [ ] **Step 4: Run adapter tests**

Run: `python -m pytest tests/test_polymarket_auth_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/connectors/polymarket_auth.py tests/test_polymarket_auth_adapter.py
git commit -m "feat: add polymarket auth readiness helpers"
```

## Task 3: SDK-Backed Adapter With Writes Disabled By Default

**Files:**
- Modify: `sports_edge_scanner/connectors/polymarket_auth.py`
- Modify: `tests/test_polymarket_auth_adapter.py`

- [ ] **Step 1: Add failing SDK adapter tests**

Append to `tests/test_polymarket_auth_adapter.py`:

```python
from sports_edge_scanner.connectors.polymarket_auth import (
    PolymarketAuthenticatedExecutionClient,
    PolymarketCredentials,
)


class FakeCredentialProvider:
    def load(self):
        return PolymarketCredentials(
            private_key="private",
            api_key="key",
            api_secret="secret",
            api_passphrase="pass",
            funder="0xfunder",
            signature_type=0,
        )


class FakeGeoblockClient:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def check(self):
        return GeoblockStatus(blocked=self.blocked, country="US" if self.blocked else "", raw={})


class FakeSdkClient:
    def __init__(self):
        self.orders = []
        self.cancels = []

    def post_order(self, **kwargs):
        self.orders.append(kwargs)
        return {"orderID": "venue-1", "status": "open"}

    def cancel(self, order_id):
        self.cancels.append(order_id)
        return {"canceled": [order_id]}

    def get_order(self, order_id):
        return {"id": order_id, "status": "open"}


def test_authenticated_client_rejects_when_live_writes_disabled():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=False,
    )

    result = client.place_order(order())

    assert result.status == "live_writes_disabled"
    assert sdk.orders == []


def test_authenticated_client_rejects_when_geoblocked():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(blocked=True),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "geoblocked"
    assert sdk.orders == []


def test_authenticated_client_normalizes_sdk_success():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "open"
    assert result.venue_order_id == "venue-1"
    assert result.raw == {"sdk_status": "open"}
    assert sdk.orders[0]["token_id"] == "token-a"


def test_authenticated_client_sanitizes_sdk_exception():
    class ExplodingSdk(FakeSdkClient):
        def post_order(self, **kwargs):
            raise RuntimeError("secret private key leaked")

    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: ExplodingSdk(),
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    result = client.place_order(order())

    assert result.status == "sdk_error"
    assert "secret" not in result.message
    assert "private" not in result.message


def test_authenticated_client_cancel_and_get_order_normalize_responses():
    sdk = FakeSdkClient()
    client = PolymarketAuthenticatedExecutionClient(
        credential_provider=FakeCredentialProvider(),
        sdk_client_factory=lambda credentials: sdk,
        geoblock_client=FakeGeoblockClient(),
        allow_live_writes=True,
    )

    cancel = client.cancel_order("venue-1")
    status = client.get_order("venue-1")

    assert cancel.status == "canceled"
    assert status.status == "open"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_auth_adapter.py -q`

Expected: FAIL because `PolymarketAuthenticatedExecutionClient` does not exist.

- [ ] **Step 3: Implement SDK-backed adapter**

Append to `sports_edge_scanner/connectors/polymarket_auth.py`:

```python
from sports_edge_scanner.core.execution import (
    ExecutionOrderStatus,
    ExecutionResult,
)


def _safe_error_message(status: str) -> str:
    return status


def _rejected_result(order: ExecutionOrder, status: str) -> ExecutionResult:
    return ExecutionResult(
        client_order_id=order.client_order_id,
        venue_order_id="",
        status=status,
        filled_notional=0.0,
        remaining_notional=order.notional,
        average_price=None,
        message=_safe_error_message(status),
        raw={},
    )


class PolymarketAuthenticatedExecutionClient:
    def __init__(
        self,
        credential_provider: CredentialProvider,
        sdk_client_factory,
        geoblock_client: PolymarketGeoblockClient,
        allow_live_writes: bool = False,
    ) -> None:
        self.credential_provider = credential_provider
        self.sdk_client_factory = sdk_client_factory
        self.geoblock_client = geoblock_client
        self.allow_live_writes = allow_live_writes

    def _sdk(self):
        credentials = self.credential_provider.load()
        return self.sdk_client_factory(credentials)

    def place_order(self, order: ExecutionOrder) -> ExecutionResult:
        if not self.allow_live_writes:
            return _rejected_result(order, "live_writes_disabled")
        try:
            geoblock = self.geoblock_client.check()
            if geoblock.blocked:
                return _rejected_result(order, "geoblocked")
            sdk = self._sdk()
            response = sdk.post_order(**map_execution_order_to_polymarket_args(order))
            if not isinstance(response, dict):
                raise ValueError("SDK response must be an object")
            venue_order_id = str(response.get("orderID") or response.get("id") or "")
            status = str(response.get("status") or "submitted")
            return ExecutionResult(
                client_order_id=order.client_order_id,
                venue_order_id=venue_order_id,
                status=status,
                filled_notional=0.0,
                remaining_notional=order.notional,
                average_price=None,
                message=status,
                raw={"sdk_status": status},
            )
        except ValueError as exc:
            if "unsupported order" in str(exc):
                return _rejected_result(order, "unsupported_order")
            return _rejected_result(order, "sdk_error")
        except Exception:
            return _rejected_result(order, "sdk_error")

    def cancel_order(self, order_id: str) -> ExecutionResult:
        if not self.allow_live_writes:
            return ExecutionResult(
                client_order_id=order_id,
                venue_order_id=order_id,
                status="live_writes_disabled",
                filled_notional=0.0,
                remaining_notional=0.0,
                average_price=None,
                message="live_writes_disabled",
                raw={},
            )
        try:
            response = self._sdk().cancel(order_id)
            status = "canceled" if isinstance(response, dict) else "submitted"
            return ExecutionResult(
                client_order_id=order_id,
                venue_order_id=order_id,
                status=status,
                filled_notional=0.0,
                remaining_notional=0.0,
                average_price=None,
                message=status,
                raw={"sdk_status": status},
            )
        except Exception:
            return ExecutionResult(
                client_order_id=order_id,
                venue_order_id=order_id,
                status="sdk_error",
                filled_notional=0.0,
                remaining_notional=0.0,
                average_price=None,
                message="sdk_error",
                raw={},
            )

    def get_order(self, order_id: str) -> ExecutionOrderStatus:
        try:
            response = self._sdk().get_order(order_id)
            if not isinstance(response, dict):
                raise ValueError("SDK response must be an object")
            return ExecutionOrderStatus(
                client_order_id=order_id,
                venue_order_id=str(response.get("id") or order_id),
                status=str(response.get("status") or "unknown"),
                raw={"sdk_status": str(response.get("status") or "unknown")},
            )
        except Exception:
            return ExecutionOrderStatus(
                client_order_id=order_id,
                venue_order_id=order_id,
                status="sdk_error",
                raw={},
            )
```

- [ ] **Step 4: Run adapter tests**

Run: `python -m pytest tests/test_polymarket_auth_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_edge_scanner/connectors/polymarket_auth.py tests/test_polymarket_auth_adapter.py
git commit -m "feat: add polymarket authenticated adapter"
```

## Task 4: Readiness-Only CLI

**Files:**
- Modify: `sports_edge_scanner/cli.py`
- Create: `tests/test_polymarket_auth_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_polymarket_auth_cli.py`:

```python
from sports_edge_scanner.cli import build_parser, main


def test_parser_supports_polymarket_auth_readiness_commands():
    parser = build_parser()

    init_args = parser.parse_args(["polymarket-auth", "init-config", "--config", "auth.json"])
    check_args = parser.parse_args(["polymarket-auth", "check", "--config", "auth.json"])
    geo_args = parser.parse_args(["polymarket-auth", "geoblock", "--json"])

    assert init_args.command == "polymarket-auth"
    assert init_args.polymarket_auth_command == "init-config"
    assert check_args.polymarket_auth_command == "check"
    assert geo_args.polymarket_auth_command == "geoblock"


def test_parser_does_not_expose_real_order_command():
    parser = build_parser()

    choices = parser._subparsers._actions[1].choices["polymarket-auth"]._subparsers._actions[1].choices

    assert "place-order" not in choices
    assert "trade" not in choices
    assert "cancel-order" not in choices


def test_polymarket_auth_init_and_check_commands(tmp_path):
    config_path = tmp_path / "polymarket_auth_config.json"

    assert main(["polymarket-auth", "init-config", "--config", str(config_path)]) == 0
    assert main(["polymarket-auth", "check", "--config", str(config_path)]) == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_polymarket_auth_cli.py -q`

Expected: FAIL because parser commands do not exist.

- [ ] **Step 3: Add CLI imports and handlers**

Modify `sports_edge_scanner/cli.py` imports:

```python
from sports_edge_scanner.connectors.polymarket_auth import (
    EnvironmentPolymarketCredentialProvider,
    PolymarketGeoblockClient,
    load_polymarket_auth_config,
    write_polymarket_auth_config_template,
)
```

Add handlers above `build_parser`:

```python
def _polymarket_auth_init_config(args: argparse.Namespace) -> int:
    try:
        path = write_polymarket_auth_config_template(Path(args.config), force=args.force)
    except FileExistsError as exc:
        print(f"polymarket-auth init-config failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _polymarket_auth_check(args: argparse.Namespace) -> int:
    try:
        config = load_polymarket_auth_config(Path(args.config))
        provider = EnvironmentPolymarketCredentialProvider(config)
        provider.load()
        credential_status = "present"
    except Exception:
        credential_status = "missing"
        config = load_polymarket_auth_config(Path(args.config))
    payload = {
        "enabled": config.enabled,
        "allow_live_writes": config.allow_live_writes,
        "require_geoblock_check": config.require_geoblock_check,
        "credential_status": credential_status,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Enabled: {payload['enabled']}")
        print(f"Allow live writes: {payload['allow_live_writes']}")
        print(f"Credential status: {payload['credential_status']}")
    return 0 if payload["enabled"] and credential_status == "present" else 1


def _polymarket_auth_geoblock(args: argparse.Namespace) -> int:
    try:
        status = PolymarketGeoblockClient().check()
    except Exception as exc:
        print(f"polymarket-auth geoblock failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(status.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Blocked: {status.blocked}")
        print(f"Country: {status.country or 'unknown'}")
    return 1 if status.blocked else 0
```

- [ ] **Step 4: Add parser group**

Inside `build_parser`, before `return parser`:

```python
polymarket_auth = subparsers.add_parser(
    "polymarket-auth",
    help="Inspect Polymarket authenticated adapter readiness.",
)
polymarket_auth_subparsers = polymarket_auth.add_subparsers(
    dest="polymarket_auth_command",
    required=True,
)

polymarket_auth_init = polymarket_auth_subparsers.add_parser(
    "init-config",
    help="Write a non-secret Polymarket auth config template.",
)
polymarket_auth_init.add_argument("--config", default="polymarket_auth_config.json")
polymarket_auth_init.add_argument("--force", action="store_true")
polymarket_auth_init.set_defaults(func=_polymarket_auth_init_config)

polymarket_auth_check = polymarket_auth_subparsers.add_parser(
    "check",
    help="Check Polymarket auth config and credential readiness.",
)
polymarket_auth_check.add_argument("--config", default="polymarket_auth_config.json")
polymarket_auth_check.add_argument("--json", action="store_true")
polymarket_auth_check.set_defaults(func=_polymarket_auth_check)

polymarket_auth_geoblock = polymarket_auth_subparsers.add_parser(
    "geoblock",
    help="Check Polymarket geographic restriction status.",
)
polymarket_auth_geoblock.add_argument("--json", action="store_true")
polymarket_auth_geoblock.set_defaults(func=_polymarket_auth_geoblock)
```

- [ ] **Step 5: Run CLI tests**

Run: `python -m pytest tests/test_polymarket_auth_cli.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sports_edge_scanner/cli.py tests/test_polymarket_auth_cli.py
git commit -m "feat: add polymarket auth readiness cli"
```

## Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section**

Append after Live Safety Core:

```markdown
## Polymarket Auth Readiness

The `polymarket-auth` command group checks whether a future authenticated adapter is configured safely. It does not place real orders and does not accept private keys or API secrets as command-line arguments.

Create a non-secret config template:

```bash
python -m sports_edge_scanner polymarket-auth init-config
```

Check local readiness:

```bash
python -m sports_edge_scanner polymarket-auth check --config polymarket_auth_config.json
```

Check geographic restriction status:

```bash
python -m sports_edge_scanner polymarket-auth geoblock --json
```

Credential values must come from environment variables named in the config. The config file stores only environment variable names and safety flags. If the geoblock check reports blocked, the adapter must reject authenticated writes.
```

- [ ] **Step 2: Run targeted tests**

Run:

```bash
python -m pytest tests/test_polymarket_auth_credentials.py tests/test_polymarket_auth_adapter.py tests/test_polymarket_auth_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile check**

Run: `python -m compileall -q sports_edge_scanner dashboard_app.py`

Expected: PASS.

- [ ] **Step 5: Run local CLI checks**

Run:

```bash
python -m sports_edge_scanner polymarket-auth init-config --config tmp_polymarket_auth_config.json --force
python -m sports_edge_scanner polymarket-auth check --config tmp_polymarket_auth_config.json --json
```

Expected:

- `init-config` exits 0.
- `check` exits 1 when credentials are absent or config is disabled.
- Output does not contain private-key/API-secret values.

Delete temporary file:

```powershell
Remove-Item -LiteralPath tmp_polymarket_auth_config.json -ErrorAction SilentlyContinue
```

- [ ] **Step 6: Review diff**

Run: `git diff --stat`

Expected: only Polymarket auth connector, CLI, tests, README, spec, and plan files changed.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: document polymarket auth readiness"
```
