# Claude 独立分流模块

适用 Mihomo；需在 `adapter.yaml` 中适配你已批准的远端代理节点名。只生成新配置，不自动部署或改动原配置。

## 推荐结构

Claude Code → 专用 HTTP 代理入口 127.0.0.1:17993 → Claude 策略组 → 手动选定的台湾节点。

网页与其他应用 → 普通入口 → Claude 域名规则集 → 同一个 Claude 策略组。

专用入口用 listener.proxy 绑定出口，进入该端口的所有目标都走 Claude，不依赖目标域名列表。因此新增认证域名、MCP 服务、遥测端点或插件仓库也不会因漏列域名而换出口。网页共享浏览器进程，仍使用域名分流。

## 文件职责

- `adapter.yaml`：唯一出口适配处。修改具体节点名即可迁移。默认手动 select，无 DIRECT、GLOBAL 或通用代理组；故障时不自动换 IP。备用节点由用户手动切换。
- `rules/core.yaml`：七个 Claude/Anthropic 专属后缀，自动覆盖子域名。
- `rules/services.yaml`：已知外部 CDN、认证及官方文档所列 Datadog 接收端，精确匹配。
- `rules/local.yaml`：个人补充，默认空。格式为 payload 下的域名列表；`+.example.com` 包含根域名和所有子域名，`host.example.com` 只匹配该主机。
- `rules/shared-optional.yaml`：共享 Sentry、Statsig、Intercom 等。默认不启用，因为其他应用也会使用；可通过 `--shared-services` 启用。
- `compose.py`：将这些文件编译进现有 Mihomo 配置的副本。生成的规则集是 inline，迁移成品无需复制绝对路径、规则文件或依赖远程规则下载。编辑源规则后需要重新编译。

## 生成预览

需要 Python 3.9+ 和 PyYAML（可通过 `pip install -r requirements.txt` 安装）。用任意已有完整 Mihomo YAML 作为输入：

```powershell
python compose.py input.yaml preview.yaml --dedicated-port 17993 --doh-fallback
```

输入、输出必须不同，已有输出不会覆盖。生成的完整配置会继承输入的节点密码和控制器密钥，请按私密配置管理，不能把它当作可公开分享的规则包。当前这个源模块不含这些凭据。

程序只接受 adapter 中明确列出的远端节点，不接受指向其他组的间接映射；缺少节点或发生同名冲突时拒绝生成。源配置需要已启用 DNS Fake-IP 且过滤列表使用 rule 模式，避免暗中改变其他应用的 DNS 行为。

载入前执行目标内核校验，例如：

```text
mihomo -t -d <原内核数据目录> -f <preview.yaml绝对路径>
```

Clash Verge 应将逻辑放进持久化的配置增强层，或把成品作为独立本地配置维护。直接覆盖自动生成的 clash-verge.yaml 会在重新生成时丢失；订阅刷新也不会自动重新编译此模块。本包没有接管订阅更新。

## Claude Code 的专用入口

在启动 Claude 的同一终端设置：

```powershell
$env:HTTP_PROXY = 'http://127.0.0.1:17993'
$env:HTTPS_PROXY = 'http://127.0.0.1:17993'
$env:ALL_PROXY = 'http://127.0.0.1:17993'
$env:NO_PROXY = 'localhost,127.0.0.1,::1'
claude
```

需先真正载入包含专用 listener 的成品。listener 仅绑定本机回环；它不是针对其他本机进程的权限隔离。若原配置启用了代理认证，沿用并核对其认证要求。

## DNS：保留域名，交给落地

同一批规则集被同时用于流量分流和 Fake-IP 过滤，域名只维护一份。规则位于通用分流之前，避免 IP 地理匹配先触发真实解析。

- HTTP CONNECT 或 SOCKS5 域名请求进入专用入口后，AnyTLS 可以携带域名交给远端处理；不需要本机先得到目标真实 IP。
- DNS 查询进入 Mihomo 且命中 Fake-IP 时，返回映射地址，连接时恢复域名；这一路目标域名通常由出口节点解析。
- `--doh-fallback` 为需要实际解析的情况增加规则集级 nameserver-policy：Cloudflare DoH 强制经 Claude 出口，默认命令启用它。它避免这些由 Mihomo 发起的目标查询使用通用本地解析器，但这是“经出口访问 Cloudflare”，不等同于“节点系统解析器”。
- 纯粹希望节点落地解析时，可省略 `--doh-fallback`；这不构成阻止任何本地解析的保证。应用自行解析、自己使用 DoH、绕过代理或直接连接 IP，仍需要流量接管或操作系统网络隔离。
- 本模块不改变代理节点自身地址的 bootstrap 解析，不要求所有系统 DNS 都经过 Claude，不改变 TUN、系统 DNS、IPv6 或 NTP。

## 覆盖与稳定性的边界

专用入口完整覆盖的是“送进这个入口的连接”。仅设置代理环境变量无法强迫所有子进程遵守代理；真正禁止旁路，需在 Linux 下使用 `bwrap` 网络命名空间与独立专用 Mihomo 进程，详见 [根 README](../../README.md#2-linux-服务器实际方案独立专用-mihomo-进程--bwrap-隔离)。

现有域名清单覆盖已知 Claude 专属域名和已确认依赖；任何静态清单都不能承诺覆盖未来所有第三方插件。不要用全局 claude/anthropic/datadog/sift 关键词、整个云厂商 IP/ASN 或 NTP 规则代替入口隔离。IP/ASN 也无法捕获未进入内核的流量。

这里手动选择节点是为保持出口稳定；若优先考虑无人值守可用性，可另外设计 fallback，但切换就可能更换 IP。节点名称白名单不能保证服务商永不更换实际出口，国家探测也不能证明两次连接的 IP 一致。

## 验证记录（2026-11-11）

用本机真实配置生成私密预览，目标内核 `alpha-91dd03a` 已通过语法与配置校验；私密预览留在工作目录，未加入分享包。包含专用入口的版本另行校验，见同目录 validation.md。

未热加载、未修改用户代理、未修改外部生产配置。

## 参考

- [Mihomo DNS 规则集与 Fake-IP](https://wiki.metacubex.one/config/dns/)
- [Mihomo mixed listener](https://wiki.metacubex.one/config/listeners/mixed/)
- [Claude Code 网络要求](https://code.claude.com/docs/en/network-config#network-access-requirements)
