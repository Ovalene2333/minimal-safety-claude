# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- 以「**极简 Safety Claude**」为主线打造开源仓库结构（聚焦 **几乎纯 Claude Code CLI 使用** + 正规 Google Play Claude Pro 订阅场景），明确指出技术配置仅作「**防手贱与兜底**」、账号存续仍取决于上游 IP/地区与真实使用合规，准确对齐实际双端架构（**Windows 共用单一 Clash Verge + 专门节点组**；**Linux 服务器单开独立 Mihomo 进程 + `bwrap` 隔离**），并纳入 **严格一号一机**、**双 ISP 家宽 `/16` 重置与台湾家宽 HiNet 置信度经验**、**浏览器 WebRTC/时区与 Windows 区域对齐** 以及 **Google Play 地区一致 & 安卓手机分身隔离技巧**；同时补充 `LICENSE` (MIT)、`.gitignore`、`.editorconfig`、`CONTRIBUTING.md`、`SECURITY.md` 与 `.github/` 模板及 CI 工作流。
- 补充 `rulesets/` 下完整的 Clash Verge Merge、Prepend Rules、DNS (`nameserver-policy` / `fake-ip-filter`) 可复制配置模板。
- 新增无第三方依赖的运行态检测脚本 `scripts/verify_mihomo.py` 与 `portable/claude-routing/tests/test_compose.py` 单元测试。

### Changed
- **精简重构为单文档核心结构**：将核心原则（P0/P1 分级）、自查验证方法（不盲信配置与 Agent）、跨端架构、部署步骤与双 ISP 家宽 `/16` 实战经验全部收敛至 [README.md](README.md)，细枝末节通过折叠块收录，移除碎片化的多篇拆分文档。
- 全面脱敏个人环境信息（本地用户路径、Profile UID、特定订阅商/节点名称、内网 DNS IP 与内部服务器路径）。
- 改进 `portable/claude-routing/compose.py` 对空 YAML 节点（`null` 值）的防御性读取，并补充 `tests/test_compose.py` 与 `scripts/verify_mihomo.py`。
- 移除仓内冗余二进制包 `portable/claude-routing.zip`（改为从源码目录直接使用）。

## [2026-11-18]

### Added
- 为 Windows Clash Verge 方案补齐全部 13 项 `claude-egress` 域名的 Cloudflare DoH `nameserver-policy` 策略（指定经 `egress` 查询），并将默认外网解析统一经代理出口。
- 同步启动守护/防火墙策略（前向规则前缀、规则集提供者与持久化 DNS 源文件哈希校验）。

## [2026-11-11]

### Added
- 完成 Windows 端代理分流初次排查，将分散的 5 条核心后缀整合为 13 项 `claude-egress` 内联域名规则集（7 个专属后缀 + 6 个外部精确主机）。
- 完成可迁移模块化生成工具 `portable/claude-routing`（`compose.py`、分层规则源、可选专用 `17993` 入口与 DoH 策略）并通过 Mihomo 内核校验。
- 完成 Linux `bwrap` 网络命名空间 + 专用 Mihomo `MATCH,egress` 方案的只读架构审查与桥接边界定界。
