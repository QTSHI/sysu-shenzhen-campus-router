# 用 AX3000T 接入中山大学深圳校区宿舍网

把宿舍墙口接到路由器，让手机、电脑连自己的 Wi-Fi 上网，日常不用再开着电脑跑锐捷——这是这次改造的目标。

这套方案在深圳校区宿舍的一台 **小米 AX3000T RD03v2** 上接通了。系统保留 **小米原厂 2.0.28**，校园认证交给 **MiniEAP**；路由器拿到校园网地址后，再通过 NAT 把网络分给自己的设备。这里的“改造”是给原厂系统增加认证服务，没有刷 OpenWrt。

```text
宿舍墙口 → 路由器 WAN → MiniEAP 认证、获取 IP → 私人 Wi-Fi / LAN → 手机、电脑
```

仓库整理了这次接入过程、诊断工具、MiniEAP 构建材料和认证服务源码。**从原厂新机开始的完整安装流程还没整理完**，其中设备检查程序 `gate.lua`、Logoff 工具和安装步骤仍需补齐。现阶段可以直接使用下面的诊断和构建工具，移植整套服务则需要自己补上这些部件。

## 先看哪一篇

**第一次下载这个仓库？从[一步步实操教程](docs/getting-started.md)开始。** 每一步都标明在哪个窗口执行、应该看到什么结果。

- **想知道怎么接通的**：[深圳校区接入过程](docs/shenzhen-campus.md)。从电脑锐捷验证讲到一根网线的接法、路由器认证和日常使用。
- **想排查自己的线路**：[工具使用与构建](docs/usage.md)。包含 Windows 协议头采集、Linux 观察器和 MiniEAP 构建。
- **想看认证服务怎么写**：[服务源码说明](stock-service/README.md)和[运行流程](docs/architecture.md)。
- **想改善 Wi-Fi、延迟和速度**：[原厂与 OpenWrt 的取舍、三种改善办法](docs/network-experience.md)。

## 这次实际做到了什么

| 项目 | 结果 |
| --- | --- |
| 路由器独立接入 | MiniEAP 认证成功，取得 IP、网关和 DNS；手机、电脑通过私人 Wi-Fi 上网 |
| 认证方式 | 该墙口可用 EAP-MD5，MiniEAP 没有启用 `rjv3` 插件 |
| 开机自动连接 | 修正关机顺序后，一次普通重启能自动认证并恢复上网 |
| 速度 | 凌晨短测：单连接下载约 123Mbps，四连接合计约 218Mbps，上传合计约 53Mbps；平均公网延迟约 18ms |
| 连续观察 | 记录了约 6 小时 35 分钟，396 次双站探测全部成功；随后电脑上的观察程序退出，24 小时测试中断 |

上午测速明显低于凌晨，原因还没定位。断电重开、拔插 WAN 后恢复、局域网设备发现和多台设备同时高负载，也留待后续测试。详细数据和测试方式放在[现场记录](docs/field-results.md)。

## 先运行工具

在仓库根目录执行，需要 Python 3.9 或更新版本：

```sh
python tools/eap_metadata.py --help
python tools/eap_metadata.py --validate examples/synthetic.jsonl
python tools/site_profile.py --json
```

第一条查看采集工具用法，第二条解析合成报文示例，第三条读取并检查匿名现场档案。这三条命令可以先在本地运行；真正采集有线认证流量，还需要 Windows 上的 Npcap，步骤见[使用说明](docs/usage.md)。

代码按功能分在这些目录：

| 目录 | 内容 |
| --- | --- |
| `tools/`、`src/` | Windows 采集前端、协议头解析器、现场档案检查 |
| `linux-observer/` | 路由器侧的被动 EAPOL 观察器 |
| `patches/`、`scripts/` | 固定版本 MiniEAP 的补丁和构建脚本 |
| `stock-service/` | 单实例认证、正常注销、关机处理和有限重试的服务源码 |
| `templates/` | 认证配置模板，使用时填写自己的配置 |

## 和南校园项目有什么关系

[RenAhsAcme/SYSU-Network-Solution](https://github.com/RenAhsAcme/SYSU-Network-Solution)介绍了广州南校园的 OpenWrt 方案。这次则记录深圳校区宿舍、RD03v2 原厂系统的做法，文档和工具独立编写。两套方案的系统、插件配置和服务管理方式有区别，见[来源与对照](REFERENCES.md)。

学校官方资料、第三方代码与许可分别见 [REFERENCES.md](REFERENCES.md)、[THIRD_PARTY.md](THIRD_PARTY.md)。项目采用 [GPL v3](LICENSE)。账号、密钥和备份的保存建议放在[安全说明](docs/security.md)，常见问题见[故障排查](docs/troubleshooting.md)。
