# 来源与许可

## MiniEAP

- 项目与作者归属：[updateing/minieap 及其贡献者](https://github.com/updateing/minieap)。
- 固定提交：`983fd4a5851d4a344fab92666c5cdb83f26b2294`。
- 上游许可：[该提交的完整 GPL v3](https://github.com/updateing/minieap/blob/983fd4a5851d4a344fab92666c5cdb83f26b2294/LICENSE)，原文保存在 `third_party/licenses/MiniEAP-GPL-3.0.txt`。
- 原 ZIP 摘要、URL及本地补丁摘要见 `third_party/minieap-source.json`。没有打包上游二进制或认证配置。
- 本地补丁修改 sockraw 绑定失败处理、套接字级混杂成员、MD5输入长度和构包返回值边界；保留上游上下文及其中的来源说明。补丁按相同 GPL v3 分发。
- 准备后的完整上游源码由固定公开地址获得，原许可证保留。下载/打补丁不代表兼容或现场部署通过。

## Npcap

Npcap由其原作者维护，使用其独立许可；本项目不捆绑 DLL、驱动、安装器或 SDK。Windows前端依据[官方API文档](https://npcap.com/guide/npcap-devguide.html)调用已安装的库；文档引用不授予重新分发Npcap的权利。

## 本项目代码

严格元数据Python解析器、重新整理的Windows前端、模板、测试、中文说明及头部观察器源码按根目录GPL v3分发。观察器保留23字节采集上限和可变sockaddr长度边界，不包含现场身份绑定。项目不是学校、小米、MiniEAP或Npcap官方发布。
