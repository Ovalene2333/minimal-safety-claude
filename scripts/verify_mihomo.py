#!/usr/bin/env python3
"""Verify Mihomo runtime routing, rule-providers, egress group safety, and proxy connections.

Uses only the Python standard library so it can run anywhere without extra dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_PROBE_HOSTS = [
    "api.anthropic.com",
    "clau.de",
    "claudemcpclient.com",
    "browser-intake-us5-datadoghq.com",
]

EXPECTED_RULE_COUNT = 13


def api_get(base_url: str, path: str, secret: str | None = None, timeout: float = 5.0) -> Any:
    """Send a GET request to the Mihomo external controller API and decode JSON."""
    url = f"{base_url.rstrip('/')}{path}"
    req = urllib.request.Request(url, method="GET")
    if secret:
        req.add_header("Authorization", f"Bearer {secret}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_provider(api_url: str, provider_name: str, secret: str | None) -> tuple[bool, str]:
    """Verify the inline domain rule-provider exists and contains the expected rule count."""
    data = api_get(api_url, "/providers/rules", secret)
    providers = data.get("providers", {})
    if provider_name not in providers:
        return False, f"Rule provider '{provider_name}' not found."
    info = providers[provider_name]
    count = info.get("ruleCount")
    behavior = info.get("behavior")
    vehicle = info.get("vehicleType")
    if behavior != "domain" or count != EXPECTED_RULE_COUNT:
        return (
            False,
            f"Provider '{provider_name}' mismatch: behavior={behavior}, vehicle={vehicle}, ruleCount={count} (expected {EXPECTED_RULE_COUNT}).",
        )
    return True, f"Provider '{provider_name}' OK: {vehicle}/{behavior}, {count} rules."


def check_rules_order(api_url: str, provider_name: str, group_name: str, secret: str | None) -> tuple[bool, str]:
    """Verify RULE-SET,<provider>,<group> appears before generic AI/MATCH rules."""
    data = api_get(api_url, "/rules", secret)
    rules = data.get("rules", [])
    target_idx = None
    generic_idx = None
    for idx, rule in enumerate(rules):
        rtype = rule.get("type", "")
        payload = rule.get("payload", "")
        proxy = rule.get("proxy", "")
        if target_idx is None and rtype == "RuleSet" and payload == provider_name and proxy == group_name:
            target_idx = idx
        if generic_idx is None and (
            "category-ai" in str(payload).lower() or rtype == "Match"
        ):
            generic_idx = idx
    if target_idx is None:
        return False, f"Rule 'RULE-SET,{provider_name},{group_name}' not found in active rules."
    if generic_idx is not None and target_idx > generic_idx:
        return (
            False,
            f"Rule order error: '{provider_name}' at index {target_idx} comes AFTER generic/AI rule at index {generic_idx}.",
        )
    return True, f"Rule order OK: 'RULE-SET,{provider_name},{group_name}' at index {target_idx}."


def check_group_safety(api_url: str, group_name: str, secret: str | None) -> tuple[bool, str]:
    """Verify the target egress group exists, has no DIRECT/GLOBAL fallback, and show active node."""
    data = api_get(api_url, f"/proxies/{urllib.request.quote(group_name)}", secret)
    members = data.get("all") or []
    now = data.get("now")
    gtype = data.get("type")
    forbidden = [m for m in members if str(m).upper() in {"DIRECT", "GLOBAL"}]
    if forbidden:
        return False, f"Group '{group_name}' contains forbidden members: {forbidden}"
    if not members:
        return False, f"Group '{group_name}' has no proxy members."
    return True, f"Group '{group_name}' ({gtype}) OK: active='{now}', members={len(members)} (no DIRECT/GLOBAL)."


def probe_hosts(proxy_url: str, api_url: str, secret: str | None, hosts: list[str]) -> list[str]:
    """Send credential-free HEAD requests through the proxy and inspect matched Mihomo connections."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    )
    results = []
    for host in hosts:
        url = f"https://{host}/"
        req = urllib.request.Request(url, method="HEAD")
        status = "unknown"
        try:
            with opener.open(req, timeout=8.0) as resp:
                status = f"HTTP {resp.status}"
        except urllib.error.HTTPError as err:
            status = f"HTTP {err.code}"
        except Exception as exc:  # noqa: BLE001
            status = f"ERR ({exc})"
        results.append(f"  - Probe {host}: {status}")

    conns = api_get(api_url, "/connections", secret).get("connections") or []
    matched = []
    host_set = set(hosts)
    for conn in conns:
        meta = conn.get("metadata") or {}
        host = meta.get("host") or meta.get("sniffHost")
        if host in host_set:
            matched.append(
                {
                    "host": host,
                    "rule": f"{conn.get('rule')} ({conn.get('rulePayload')})",
                    "chains": conn.get("chains"),
                }
            )
    results.append(f"  - Recent matching connections in Mihomo: {json.dumps(matched, ensure_ascii=False)}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Mihomo runtime configuration for Claude routing.")
    parser.add_argument("--api", default="http://127.0.0.1:9097", help="Mihomo external controller URL")
    parser.add_argument("--secret", default=None, help="Mihomo controller secret if configured")
    parser.add_argument("--provider", default="claude-egress", help="Rule-provider name to verify")
    parser.add_argument("--group", default="egress", help="Target proxy group name to verify")
    parser.add_argument("--proxy", default="http://127.0.0.1:7890", help="Local proxy URL used with --probe")
    parser.add_argument("--probe", action="store_true", help="Send credential-free HEAD probes and check /connections")
    args = parser.parse_args()

    checks = [
        check_provider(args.api, args.provider, args.secret),
        check_rules_order(args.api, args.provider, args.group, args.secret),
        check_group_safety(args.api, args.group, args.secret),
    ]

    all_ok = True
    for ok, msg in checks:
        prefix = "[PASS]" if ok else "[FAIL]"
        print(f"{prefix} {msg}")
        all_ok = all_ok and ok

    if args.probe:
        print("[INFO] Running credential-free proxy probes...")
        for line in probe_hosts(args.proxy, args.api, args.secret, DEFAULT_PROBE_HOSTS):
            print(line)

    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"[ERROR] Failed to reach Mihomo API: {exc}", file=sys.stderr)
        sys.exit(2)
