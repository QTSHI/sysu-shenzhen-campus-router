# 原厂服务的离线生成器

本目录保留服务状态机的四层源码，方便审查正常注销、关机处理和有界恢复策略。入口只在本机生成 shell 文本；不会连接设备、安装服务、执行生成物、发认证或清除失败锁。四个原文件按原字节保存，父模块的 SHA256 校验也保留。

| 文件 | 作用 |
| --- | --- |
| `stock_persistent_runner.py` | 基础监督进程、子进程归属、协议头观察和失败锁存 |
| `stock_persistent_runner_logoff.py` | 认证前正常 Logoff、30 秒冷却与启动条件等待 |
| `stock_persistent_runner_shutdown.py` | 正常关机的早期 K01 钩子，先停止自己的会话再注销 |
| `stock_persistent_runner_rolling_candidate.py` | v2 状态格式与滚动恢复预算；文件名保留原审查名称 |

这些 Python 源码及新增入口按根目录 GPL v3 许可分发。MiniEAP 自身的来源和许可见 [`THIRD_PARTY.md`](../THIRD_PARTY.md)。本目录没有捆绑第三方可执行文件。

## 适用假设与缺少的部件

这是固定硬件布局的参考实现，不能直接当作通用安装器。它假设有线 WAN 接口是 `eth0.1`，服务目录为 `/data/usr/sysu-campus-auth/service`，RAM 状态目录为 `/tmp/sysu-campus-service`，并依赖对应固件的 BusyBox、Lua、OpenSSL、ubus、`/proc` 与 sysfs 行为。

生成物还要求以下外部部件；本目录均不提供：

- 已审查的 `gate.lua`，用于检查硬件、桥隔离、管理入口、安全配置和客户端归属。
- MiniEAP、协议头观察器及与其真实文件匹配的 SHA256。
- 只在本机输入并安全保存的认证配置。仓库没有可用账号、密码、私钥或现场认证配置。
- 正常 Logoff 工具、文件 seal、权限和受控启动环境。

Logoff 层仍保留固定的 `LOGOFF_SHA`，表示其原审查构建身份。这个工具没有随仓库分发；公开的协议头观察器也不是 Logoff 工具。复用时需要针对自己的接口和硬件重新审查依赖并固定摘要，不能用空实现或关闭校验来跳过这一条件。这里提供的输入摘要只用于 MiniEAP 和观察器，不会自动适配上述缺少的部件。

## 仅生成文本

无参数和 `--help` 只显示帮助：

```text
python stock-service/render_runner.py --help
```

显式选择生成 runner 或 shutdown，并把两个占位值替换为自己构建文件的 64 位小写十六进制摘要：

```text
python stock-service/render_runner.py --render --artifact runner --minieap-sha256 YOUR_64_HEX_DIGEST --observer-sha256 YOUR_64_HEX_DIGEST --output runner.sh
python stock-service/render_runner.py --render --artifact shutdown --minieap-sha256 YOUR_64_HEX_DIGEST --observer-sha256 YOUR_64_HEX_DIGEST --output shutdown.sh
```

输出文件必须不存在，已有文件不会被覆盖；省略 `--output` 时仅向标准输出写源码。生成和语法检查都不能证明某台路由器兼容，也不代表已经认证或联网。

## 状态与恢复策略

v2 状态保留真实累计 `attempt` 和 `recovery_used`，并增加最近窗口计数、下一次允许恢复的 uptime 和预算暂停标志。旧 v1 parser 会拒绝 v2，不能把累计计数截断后交给旧工具。监控器、验收器与状态 parser 必须同时使用匹配版本。

对于已成功会话的链路恢复，参考策略在 1800 秒内最多预留两次恢复工作流，并要求距离上次实际认证进程启动至少 300 秒。预算用尽时进入 `network-paused`，等待预算恢复；EAP Failure、认证超时或未知的尝试仍持久锁存，不会自动清锁或无限重启。预算属于同一 boot，不能推导为跨重启的永久状态。

这一策略不设置 LAN 设备数上限，也不修改 Wi-Fi 广播、无线隔离、QoS 或带宽限制。它不能证明无限设备容量、物理拔插恢复或 24 小时稳定性。实际已测范围见 [`docs/field-results.md`](../docs/field-results.md)。

现有客户端的父 PID 不能交给新监督进程。本目录不提供运行中的 PID 接管或安装入口；需要迁移时应另行审查备份、版本配套、正常注销、独立管理通路和回滚方案。

## 离线测试

```text
python -m unittest discover -s stock-service -p "test_*.py" -v
```

测试核对四层精确源码摘要、生成结果和 v2 累计计数；系统有 `sh` 时仅执行 `sh -n` 语法检查，不运行 shell 内容。没有网络或设备测试。
