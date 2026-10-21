# 参考资料与相关项目

整理日期：2026-10-21。

## 学校的接入说明

- [个人用户有线网络接入](https://inc.sysu.edu.cn/service/wired-network-access)：学生有线接入流程、Windows 客户端下载、NetID 认证和自动获取 IP 的要求。
- [锐捷客户端 FAQ](https://inc.sysu.edu.cn/cat/152)：Windows 原生有线 802.1X 与锐捷冲突、认证后获取 DHCP 地址等问题的说明。
- [学生搬迁校园网络指引](https://inc.sysu.edu.cn/article/1459)，2023-07-05：当时把深圳学生宿舍与南校园归为锐捷接入环境。本项目据此选择官方客户端起步，再用当前墙口的记录判断认证方法。

## 南校园的 OpenWrt 方案

[RenAhsAcme/SYSU-Network-Solution](https://github.com/RenAhsAcme/SYSU-Network-Solution)以广州南校园为背景，介绍了通过 OpenWrt 接入校园网的做法。它与本项目最直接的差别是：

| | 南校园项目 | 本次深圳方案 |
| --- | --- | --- |
| 路由器系统 | OpenWrt | RD03v2 原厂 2.0.28 |
| MiniEAP 配置 | 示例启用 `rjv3` 插件 | 当前墙口使用标准 MiniEAP 即可认证 |
| 服务管理 | OpenWrt 服务机制 | 原厂系统上的定制启动、关机及恢复流程 |

本次参考其思路，文档和工具独立编写。南校园项目的 IPv6、吞吐和终端限制等结论，仍属于作者当时的环境；本项目的实测数据见[现场记录](docs/field-results.md)。

核对的版本为 `be6990d3e34e39811db622aed32e8d088db9e8cb`，便于之后对照：

- [README](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/README.md)
- [软件包 Makefile](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/Makefile)
- [GPL v3](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/LICENSE)
- [CC BY-NC-SA 4.0](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/LICENSE_CC)

该版本同时附有两份许可证，未明确标注逐文件归属；这里通过链接和文字对照介绍它，未复制其代码、文档或图片。

## 代码与工具来源

- **MiniEAP**：上游、固定提交和补丁说明在 [THIRD_PARTY.md](THIRD_PARTY.md) 与[源码记录](third_party/minieap-source.json)。
- **Npcap**：[官网](https://npcap.com/)和[开发文档](https://npcap.com/guide/npcap-devguide.html)。安装器和驱动需另行从官网获取。
- **无线带宽**：[Intel 关于 160MHz 环境因素的说明](https://www.intel.com/content/www/us/en/support/articles/000092185/wireless.html)。
- **负载下的延迟**：[OpenWrt SQM 文档](https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm)，介绍队列管理的用途、CPU 开销和卸载取舍。
