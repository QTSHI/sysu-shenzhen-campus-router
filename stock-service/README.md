# 原厂系统上的认证服务

MiniEAP 负责完成一次认证；这部分代码负责让它作为路由器服务长期运行：开机等待网口就绪，启动一个客户端，成功后保持会话，关机时正常注销，断线后按预算尝试恢复。

这里保存了现场使用的四层 Python 源码，以及一个将它们组合成 shell 脚本的入口。**目前能直接做的是在本地生成脚本；完整安装到另一台路由器，还缺设备检查、Logoff 等配套部件。**

## 源码怎么读

| 文件 | 在上一层基础上增加什么 |
| --- | --- |
| `stock_persistent_runner.py` | 管理唯一客户端，观察认证结果，记录失败 |
| `stock_persistent_runner_logoff.py` | 启动前正常注销旧会话，冷却 30 秒并等待条件就绪 |
| `stock_persistent_runner_shutdown.py` | 通过 K01 关机钩子，按顺序停止客户端并注销 |
| `stock_persistent_runner_rolling_candidate.py` | v2 状态和一定时间内的恢复次数预算 |

文件名保留了开发时的层次。后面的文件引用前面的实现，生成入口会核对四个文件的原字节摘要，所以修改源码后也需要同步对应摘要。

## 为什么不能只上传 runner.sh 就完成部署

脚本按本次原厂环境编写，使用以下位置：

- WAN：`eth0.1`
- 程序和配置：`/data/usr/sysu-campus-auth/service`
- 临时状态：`/tmp/sysu-campus-service`

它调用原厂固件的 BusyBox、Lua、OpenSSL、ubus、`/proc` 和 sysfs，同时还依赖：

| 配套部件 | 用途 | 仓库中的状态 |
| --- | --- | --- |
| `gate.lua` | 检查设备、WAN/LAN 分离、管理入口及进程归属 | 待通用化整理 |
| MiniEAP、协议头观察器 | 认证、记录请求与结果 | 提供构建源码，需要自行编译 |
| Logoff 工具 | 在接口上发送正常注销帧 | 未收录；源码里固定了现场构建的 `LOGOFF_SHA` |
| 账号配置、文件 seal、安装和启动配置 | 保存凭据、确认程序版本、接入开关机流程 | 需要针对设备准备 |

`render_runner.py` 接受的两个摘要只对应 MiniEAP 和观察器。补齐其余部件后，还要让实际文件、路径、摘要和启动顺序相互对应。协议头观察器与 Logoff 工具的用途不同，不能互相替代。

## 生成脚本

先查看参数：

```sh
python stock-service/render_runner.py --help
```

准备好自己构建的两个文件摘要后，替换下面的占位符：

```sh
python stock-service/render_runner.py --render --artifact runner --minieap-sha256 YOUR_MINIEAP_SHA256 --observer-sha256 YOUR_OBSERVER_SHA256 --output runner.sh
python stock-service/render_runner.py --render --artifact shutdown --minieap-sha256 YOUR_MINIEAP_SHA256 --observer-sha256 YOUR_OBSERVER_SHA256 --output shutdown.sh
```

摘要格式为 64 位小写十六进制。输出文件名要用新的；省略 `--output` 时，源码会打印到终端。这一步生成文本，不会连接路由器。

## 断线以后怎样处理

成功认证后保持原客户端运行，观察日志换段也不会重启认证。只有已经成功过的会话，才会进入链路恢复流程。

v2 的预算是：**同一次开机内，任意连续 30 分钟内最多预留两次恢复流程，距离上次实际认证启动至少 5 分钟**。预算耗尽时进入 `network-paused`，等窗口恢复。明确的 EAP Failure、认证超时和结果不明的尝试会留下故障记录并停止，留给使用者排查。

状态中的 `attempt`、`recovery_used` 是累计值，另外的字段记录当前窗口次数和下次允许恢复的时间。读取它们的监控程序也需要使用 v2 格式；v1 parser 不兼容。

现场已经测试普通重启后自动认证。拔插 WAN 后的恢复仍需实测，完整结果见[现场记录](../docs/field-results.md)。这套预算只管理校园认证，LAN 设备数量由无线、DHCP 和路由配置决定。

## 修改和测试

```sh
python -m unittest discover -s stock-service -p "test_*.py" -v
```

测试检查源码摘要、生成内容和 v2 累计计数；系统有 `sh` 时还会做 shell 语法检查。移交正在运行的会话时，要通过正常注销和重新启动完成，新进程不能直接继承旧客户端的父进程关系。

本目录采用根目录的 GPL v3 许可。MiniEAP 来源见 [`THIRD_PARTY.md`](../THIRD_PARTY.md)。
