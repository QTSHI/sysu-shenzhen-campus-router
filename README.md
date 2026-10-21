# 用 AX3000T 接入中山大学深圳校区宿舍网

记录中山大学深圳校区宿舍、小米 AX3000T RD03v2 原厂系统的一次校园网接入实践，提供协议头诊断工具、MiniEAP 构建材料和认证服务源码。

目标是让手机、电脑通过自己的 Wi-Fi 上网，日常无需开着电脑跑锐捷。已有现场结果来自一台保留 **小米原厂 2.0.28** 的设备；完整新机安装流程仍需补齐。

[项目概览](#项目概览) · [快速开始](#快速开始) · [使用说明](#使用说明) · [开发与验证](#开发与验证) · [目录结构](#目录结构) · [项目文档](#项目文档) · [当前边界](#当前边界)

## 项目概览

MiniEAP 完成校园认证，路由器取得地址后通过 NAT 为设备提供网络，没有刷 OpenWrt：

```text
宿舍墙口 → 路由器 WAN → MiniEAP 认证、获取 IP → 私人 Wi-Fi / LAN → 手机、电脑
```

| 项目 | 已有现场记录 |
| --- | --- |
| 独立接入 | MiniEAP 认证成功，取得 IP、网关和 DNS，手机、电脑通过私人 Wi-Fi 上网 |
| 认证方式 | 该墙口可用 EAP-MD5，没有启用 `rjv3` 插件 |
| 开机连接 | 修正关机顺序后，一次普通重启能自动认证并恢复上网 |
| 速度 | 凌晨短测：单连接下载约 123Mbps、四连接合计约 218Mbps、上传合计约 53Mbps，平均公网延迟约 18ms |
| 连续观察 | 约 6 小时 35 分钟，396 次双站探测成功，随后电脑观察程序退出，24 小时测试中断 |

测试方式和原始记录边界见 [现场记录](docs/field-results.md)，这些结果不代表所有墙口、设备或固件。

## 快速开始

离线工具需要 Python 3.9 或更新版本。首次下载后进入仓库：

```sh
git clone https://github.com/QTSHI/sysu-shenzhen-campus-router.git
cd sysu-shenzhen-campus-router
python tools/eap_metadata.py --help
python tools/eap_metadata.py --validate examples/synthetic.jsonl
python tools/site_profile.py --json
```

以上命令分别查看工具用法、解析合成报文示例、检查匿名现场档案，无需连接路由器。真正采集有线认证流量需要 Windows 与 Npcap；Linux 观察器及构建工具另有环境要求，见 [工具使用与构建](docs/usage.md)。

## 使用说明

**首次使用从[一步步实操教程](docs/getting-started.md)开始。** 每一步都标明执行窗口与预期结果。

- 了解怎么接通：[深圳校区接入过程](docs/shenzhen-campus.md)，包含电脑锐捷验证、网线接法、路由器认证和日常使用。
- 排查线路或构建工具：[工具使用与构建](docs/usage.md)，包含 Windows 协议头采集、Linux 观察器和 MiniEAP 构建。
- 阅读认证服务：[服务源码说明](stock-service/README.md)和[运行流程](docs/architecture.md)。
- 改善 Wi-Fi、延迟与速度：[网络体验与方案取舍](docs/network-experience.md)。

## 开发与验证

从仓库根目录运行离线检查：

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s stock-service -p 'test_*.py' -v
```

[自动检查](.github/workflows/ci.yml)覆盖 Python 3.9/3.12 的解析器、公共模板、服务渲染器、合成示例及 Linux C 观察器。ARM/MiniEAP 构建与现场认证需要对应环境，不能由离线测试替代。已有检查记录见 [VALIDATION.md](VALIDATION.md)，开发约定见 [贡献指南](CONTRIBUTING.md)。

## 目录结构

| 目录 | 内容 |
| --- | --- |
| `tools/`、`src/` | Windows 采集前端、协议头解析器和现场档案检查 |
| `linux-observer/` | 路由器侧被动 EAPOL 观察器 |
| `patches/`、`scripts/` | 固定版本 MiniEAP 补丁和构建工具 |
| `stock-service/` | 单实例认证、正常注销、关机处理与有限重试服务 |
| `templates/` | 需填写自身参数的认证配置模板 |
| `docs/` | 实操、现场记录、架构、排障与安全说明 |
| `tests/` | 离线解析器、档案与公共模板测试 |

## 项目文档

- [实操教程](docs/getting-started.md)、[故障排查](docs/troubleshooting.md)与[安全说明](docs/security.md)。
- [现场记录](docs/field-results.md)与[验证记录](VALIDATION.md)：分别记录联网测试和代码检查。
- [来源与对照](REFERENCES.md)、[第三方代码](THIRD_PARTY.md)与 [GPL v3](LICENSE)：学校资料、第三方来源及许可。
- [贡献指南](CONTRIBUTING.md)：问题反馈、验证、源码清单与生成文件约定。

[RenAhsAcme/SYSU-Network-Solution](https://github.com/RenAhsAcme/SYSU-Network-Solution)介绍广州南校园的 OpenWrt 方案。本仓库的深圳校区 RD03v2 原厂系统实践、文档与工具独立编写，两者的系统、插件配置和服务管理方式有区别，详见来源与对照。

## 当前边界

- **这不是完整的新机安装器**：设备检查程序 `gate.lua`、Logoff 工具和部分安装步骤仍需补齐；移植整套服务需要自行补上这些部件。
- 上午测速低于凌晨，原因尚未定位；冷启动、拔插 WAN 恢复、设备发现及多设备同时高负载仍待测试。
- 24 小时观察未完成；已有六小时记录不能当作全天稳定性证明。
- 账号、密钥、抓包和本地备份不随仓库提供，保存与脱敏方式见安全说明。
