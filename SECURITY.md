# Security Policy

## 敏感信息与凭据保护（重要）

本仓库仅收纳**脱敏后的规则集、配置模板、结构化架构文档与离线配置生成工具**。提交任何 Issue、Pull Request 或文档更新前，请务必确认不包含以下内容：

- 机场或自建节点的**订阅 URL、服务器地址、端口、密码、UUID、TLS SNI / 公私钥**
- Mihomo / Clash Verge 的**外部控制 API 密钥（`secret`）**
- 账号凭据：**OAuth Token、Session Cookie、`ANTHROPIC_API_KEY`**
- 包含个人路径、内网 DNS IP（如校园网/企业内网解析器地址）、主机名或业务会话标识的完整运行配置文件（如 `clash-verge.yaml`）

如果不小心将包含凭据的配置文件提交到了公开分支，请立即：
1. 吊销并轮换对应的代理密码、订阅链接、控制器密钥或 API Key。
2. 使用 `git filter-repo` 等工具清理历史提交（仅靠新提交删除无法抹去历史记录）。

## 安全边界声明

1. **域名分流不等于完全防泄漏**：仅靠 `RULE-SET` 或 `HTTP_PROXY` 环境变量无法强制接管绕过系统代理的应用、直连 IP 请求、UDP/QUIC 流量或客户端自带 DoH。如需强隔离，请参考 [README 中的 Linux 沙箱方案](README.md#2-linux-服务器实际方案独立专用-mihomo-进程--bwrap-隔离)。
2. **专用端口权限边界**：`127.0.0.1:17993` 等回环监听端口面向本机所有进程开放，不构成进程间权限隔离。
3. **桥接通道风险**：在网络命名空间隔离架构中，任何向宿主暴露的 Unix Socket 或局部端口桥接（如实验用 tmux RPC、本地模型服务端口）都会扩大信任边界，运行不可信项目代码前请先评估桥接面。

## 漏洞与风险报告

如果你在本项目的配置生成脚本（`compose.py`）、规则集定义或隔离架构文档中发现安全隐患（例如规则绕过、默认不安全配置、模板误导等），请勿直接在公开 Issue 中贴出可被利用的私密环境细节：

- 可以通过 GitHub Private Vulnerability Reporting（Security Advisories）私密反馈，或在脱敏后提交 Issue 讨论。
- 报告时请尽量附上最小复现 YAML 片段（已脱敏）与目标 Mihomo 内核版本号。
