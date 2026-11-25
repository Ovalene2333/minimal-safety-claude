# Contributing Guide

欢迎提交 Issue 或 Pull Request 来完善 Claude / Claude Code 的分流规则、DNS 策略、校验脚本或排障指南。

## 贡献范围

- **域名清单维护**：补充新确认的 Claude 官方域名、认证域名、CDN 或可选遥测域名（需附官方来源或抓包/日志验证依据）。
- **工具与测试改进**：改进 `portable/claude-routing/compose.py`、`scripts/verify_mihomo.py` 或补充自动化测试用例。
- **文档与排障经验**：补充不同客户端（Claude Code CLI / Claude Desktop / Web）、系统环境（Windows / WSL2 / macOS / Linux）下的实测与排障记录。

## 域名分类原则

为避免误伤其他应用流量，请严格区分以下层级：

| 目标文件 | 适用范围 | 规则示例 |
|---|---|---|
| `portable/claude-routing/rules/core.yaml` | Anthropic / Claude 专属域名后缀 | `+.anthropic.com`、`+.claude.ai` |
| `portable/claude-routing/rules/services.yaml` | 明确仅用于 Claude 业务的外部精确主机 | `anthropic.auth0.com`、`servd-anthropic-website.b-cdn.net` |
| `portable/claude-routing/rules/shared-optional.yaml` | 与其他软件共享的第三方服务（默认不启用） | `+.sentry.io`、`+.intercom.io` |
| `portable/claude-routing/rules/local.yaml` | 个人自定义扩展（仓库内保持为空） | `[]` |

**禁止加入**：过于宽泛的全局关键词（如 `DOMAIN-KEYWORD,claude`、`DOMAIN-KEYWORD,datadog`、`DOMAIN-KEYWORD,sentry`）或整个云厂商 ASN/IP 段，以免劫持无关软件流量。

## 提交前检查清单

1. **严格脱敏**：确认未包含任何真实节点名、密码、订阅链接、用户目录路径或内网 IP。
2. **同步更新规则副本**：如果新增了核心或精确服务域名，请同步检查：
   - `rulesets/claude-egress.yaml`
   - `rulesets/clash-verge-merge.example.yaml`
   - `rulesets/dns-config.example.yaml`
   - `portable/claude-routing/rules/{core,services}.yaml`
3. **运行测试与格式检查**：
   ```bash
   python -m unittest discover -s portable/claude-routing/tests -v
   ```
4. **内核配置校验**（如修改了规则或 `compose.py`）：
   ```bash
   mihomo -t -d <mihomo-data-dir> -f <generated-preview.yaml>
   ```
