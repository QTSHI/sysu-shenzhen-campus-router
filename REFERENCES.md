# 来源、适用范围与相关项目

核对日期：2026-10-21。学校文件提供背景与官方操作要求；本项目的具体墙口协议、硬件和运行结果以独立现场证据为准。

## 学校官方资料

1. [个人用户有线网络接入](https://inc.sysu.edu.cn/service/wired-network-access)：学生使用NetID与认证客户端，IPv4自动获取；客户端下载入口以学校网页为准。本项目不重新分发官方客户端安装包。
2. [学生锐捷认证客户端FAQ](https://inc.sysu.edu.cn/cat/152)：指出Windows原生有线802.1X可能与锐捷争用；认证成功后还需成功获取DHCP地址。本文只引用相关诊断原则，不把历史FAQ中的全局重置、驱动卸载或关闭安全防护当作常规步骤。
3. [学生搬迁校园网络指引](https://inc.sysu.edu.cn/article/1459)，2023-07-05：当时将深圳学生宿舍归入锐捷接入环境，与南校园同类。这是历史分类，不证明今天任一墙口的开放状态、EAP方法或带宽配额。

## 广州南校园相关项目

可作对照的南校园项目是[RenAhsAcme/SYSU-Network-Solution](https://github.com/RenAhsAcme/SYSU-Network-Solution)。作者README明确说明以广州南校园的学生接入环境为基础。

本次只读核对版本为`be6990d3e34e39811db622aed32e8d088db9e8cb`：

- [固定版本README](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/README.md)
- [软件包Makefile](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/Makefile)
- [GPLv3许可证](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/LICENSE)
- [另附的CC BY-NC-SA 4.0许可证](https://github.com/RenAhsAcme/SYSU-Network-Solution/blob/be6990d3e34e39811db622aed32e8d088db9e8cb/LICENSE_CC)

两种许可文件并存，已读说明没有给出明确逐文件映射。本项目只链接并原创概括技术差异，没有复制其文档、图片或脚本，也不将其双许可解释为本项目许可。

| 方面 | 南校园相关项目 | 深圳现场项目 |
| --- | --- | --- |
| 系统路线 | OpenWrt及其软件包、服务管理 | RD03v2原厂2.0.28上的定制服务 |
| 认证方式 | 文档示例启用MiniEAP的rjv3插件 | 本墙口标准MiniEAP、未启用rjv3实测成功 |
| 生命周期 | OpenWrt服务管理示例 | 单实例归属检查、正常Logoff、失败停止、有限恢复 |
| 网络能力 | 作者南校园环境中的独立结论 | 仅采用深圳现场已验证项目；IPv6、带宽等不继承 |

相关项目中关于DNS、IPv6、吞吐、客户端限制或其他扩展路线的结论，不构成本项目的实测结果。

## 直接代码来源

本项目使用的MiniEAP上游、固定提交、补丁和许可证见[THIRD_PARTY.md](THIRD_PARTY.md)与[构建来源文件](third_party/minieap-source.json)。MiniEAP构建材料与本项目原创工具按其相应许可证处理。

Npcap来自[Npcap官网](https://npcap.com/)，SDK行为参考其[开发文档](https://npcap.com/guide/npcap-devguide.html)。本项目不打包Npcap安装器、SDK或驱动。

无线与排队改善的背景参考：[Intel对固定160MHz环境因素的说明](https://www.intel.com/content/www/us/en/support/articles/000092185/wireless.html)、[OpenWrt SQM文档](https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm)。后者解释通用取舍，不代表本原厂固件已安装或支持CAKE/SQM。
