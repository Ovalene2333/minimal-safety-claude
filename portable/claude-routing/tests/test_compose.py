"""Unit tests for portable/claude-routing/compose.py."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import compose  # noqa: E402


def make_base_config() -> dict:
    return {
        "mixed-port": 7890,
        "proxies": [
            {"name": "TW-ISP-Node-01", "type": "anytls", "server": "tw1.example.invalid", "port": 443},
            {"name": "TW-ISP-Node-02", "type": "anytls", "server": "tw2.example.invalid", "port": 443},
        ],
        "proxy-groups": [
            {"name": "Proxies", "type": "select", "proxies": ["TW-ISP-Node-01"]},
        ],
        "rules": [
            "DOMAIN-SUFFIX,anthropic.com,egress",
            "PROCESS-NAME,claude.exe,egress",
            "GEOSITE,category-ai,Proxies",
            "MATCH,Proxies",
        ],
        "dns": {
            "enable": True,
            "enhanced-mode": "fake-ip",
            "fake-ip-filter-mode": "rule",
            "fake-ip-filter": ["geosite:cn,real-ip"],
            "nameserver-policy": {
                "+.anthropic.com": ["https://1.1.1.1/dns-query#egress"],
                "geosite:cn": ["https://223.5.5.5/dns-query"],
            },
        },
    }


def make_adapter() -> dict:
    return {
        "name": "Claude",
        "type": "select",
        "proxies": ["TW-ISP-Node-01", "TW-ISP-Node-02"],
    }


class ComposeTests(unittest.TestCase):
    def test_shared_sources_and_cleanup_old_rules(self) -> None:
        cfg = make_base_config()
        res = compose.compose(cfg, make_adapter(), shared=False, doh=True, dedicated_port=17993)

        self.assertIn("local-claude-core", res["rule-providers"])
        self.assertIn("local-claude-services", res["rule-providers"])
        self.assertNotIn("local-claude-shared-optional", res["rule-providers"])
        self.assertNotIn("local-claude-local", res["rule-providers"])

        # Same source providers used in traffic rules, fake-ip-filter, and nameserver-policy
        self.assertEqual(res["rules"][0], "RULE-SET,local-claude-core,Claude")
        self.assertEqual(res["rules"][1], "RULE-SET,local-claude-services,Claude")
        self.assertNotIn("DOMAIN-SUFFIX,anthropic.com,egress", res["rules"])
        self.assertNotIn("PROCESS-NAME,claude.exe,egress", res["rules"])
        self.assertIn("PROCESS-NAME,claude.exe,Claude", res["rules"])

        self.assertEqual(
            res["dns"]["fake-ip-filter"][:2],
            ["RULE-SET,local-claude-core,fake-ip", "RULE-SET,local-claude-services,fake-ip"],
        )
        self.assertNotIn("+.anthropic.com", res["dns"]["nameserver-policy"])
        self.assertIn("geosite:cn", res["dns"]["nameserver-policy"])
        self.assertIn("rule-set:local-claude-core,local-claude-services", res["dns"]["nameserver-policy"])

        # Dedicated loopback listener bound directly to Claude
        self.assertEqual(len(res["listeners"]), 1)
        self.assertEqual(res["listeners"][0]["listen"], "127.0.0.1")
        self.assertEqual(res["listeners"][0]["port"], 17993)
        self.assertEqual(res["listeners"][0]["proxy"], "Claude")

    def test_shared_services_flag_and_no_process_rules(self) -> None:
        res = compose.compose(
            make_base_config(), make_adapter(), shared=True, doh=False, processes=False
        )
        self.assertIn("local-claude-shared-optional", res["rule-providers"])
        self.assertFalse(any(r.startswith("PROCESS-NAME,") for r in res["rules"]))
        self.assertNotIn("rule-set:local-claude-core,local-claude-services,local-claude-shared-optional", res["dns"]["nameserver-policy"])

    def test_rejects_missing_proxy_node(self) -> None:
        adapter = make_adapter()
        adapter["proxies"].append("NON_EXISTENT")
        with self.assertRaisesRegex(ValueError, "Proxy node missing"):
            compose.compose(make_base_config(), adapter)

    def test_rejects_direct_or_indirect_targets(self) -> None:
        for forbidden in ("DIRECT", "REJECT", "GLOBAL", "Claude"):
            adapter = make_adapter()
            adapter["proxies"] = [forbidden]
            with self.assertRaises(ValueError):
                compose.compose(make_base_config(), adapter)

    def test_rejects_group_name_collision(self) -> None:
        cfg = make_base_config()
        cfg["proxy-groups"].append({"name": "Claude", "type": "select", "proxies": ["TW-ISP-Node-01"]})
        with self.assertRaisesRegex(ValueError, "already exists"):
            compose.compose(cfg, make_adapter())

    def test_rejects_invalid_dns_modes(self) -> None:
        cfg_no_fakeip = make_base_config()
        cfg_no_fakeip["dns"]["enhanced-mode"] = "redir-host"
        with self.assertRaisesRegex(ValueError, "fake-ip"):
            compose.compose(cfg_no_fakeip, make_adapter())

        cfg_blacklist = make_base_config()
        cfg_blacklist["dns"]["fake-ip-filter-mode"] = "blacklist"
        with self.assertRaisesRegex(ValueError, "rule mode"):
            compose.compose(cfg_blacklist, make_adapter())

    def test_rejects_port_and_listener_collisions(self) -> None:
        with self.assertRaisesRegex(ValueError, "already in use"):
            compose.compose(make_base_config(), make_adapter(), dedicated_port=7890)

        cfg = make_base_config()
        cfg["listeners"] = [{"name": "claude-dedicated", "type": "mixed", "listen": "127.0.0.1", "port": 18000}]
        with self.assertRaisesRegex(ValueError, "already in use"):
            compose.compose(cfg, make_adapter(), dedicated_port=17993)

    def test_rejects_insecure_tls_or_dialer_chain(self) -> None:
        cfg_cert = make_base_config()
        cfg_cert["proxies"][0]["skip-cert-verify"] = True
        with self.assertRaisesRegex(ValueError, "Certificate verification"):
            compose.compose(cfg_cert, make_adapter())

        cfg_dialer = make_base_config()
        cfg_dialer["proxies"][0]["dialer-proxy"] = "relay"
        with self.assertRaisesRegex(ValueError, "dialer-chain"):
            compose.compose(cfg_dialer, make_adapter())

    def test_handles_null_yaml_sections_gracefully(self) -> None:
        cfg = copy.deepcopy(make_base_config())
        cfg["listeners"] = None
        cfg["rule-providers"] = None
        cfg["dns"]["nameserver-policy"] = None
        res = compose.compose(cfg, make_adapter(), dedicated_port=17993)
        self.assertEqual(len(res["listeners"]), 1)
        self.assertIn("local-claude-core", res["rule-providers"])


if __name__ == "__main__":
    unittest.main()
