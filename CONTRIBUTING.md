# 贡献指南

## 开始之前

本仓库记录深圳校区宿舍、AX3000T RD03v2 原厂系统的一次接入实践。先阅读 [README](README.md)、[实操教程](docs/getting-started.md)和[安全说明](docs/security.md)，保留设备、系统、校区与测试条件的区别。

## 开发与验证

从仓库根目录执行：

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s stock-service -p 'test_*.py' -v
python tools/eap_metadata.py --validate examples/synthetic.jsonl
python tools/site_profile.py --json
```

Linux 观察器及 MiniEAP 构建需要 Linux/对应交叉编译环境，见 [工具使用与构建](docs/usage.md)及[验证记录](VALIDATION.md)。本地测试通过不能证明某个墙口、设备或固件已经接通。

## 提交 Issue

使用问题反馈或功能建议模板，说明设备型号、固件、操作系统、文档步骤和预期/实际结果。只提供脱敏协议头摘要与最小复现，不提交账号、密码、私钥、完整配置、抓包或认证负载。

## 提交 PR

说明目的、影响工具或文档，以及实际执行的检查。文档区分实测、推断和待验证项目，保留现场记录的时长与限制；功能改动附相关测试结果，只改文档时核对链接、命令和源码。第三方来源与许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 数据与生成文件

- 本地凭据、日志、抓包、二进制与备份遵守现有忽略规则，不加入版本控制。
- 认证脚本从现有 renderer 生成，不手工修改生成结果；保留四层源码摘要约束。
- 修改发布文件后，同步更新 `SOURCE-MANIFEST.json` 中的文件大小与 SHA256；清单不记录自身。
- 验证记录保留历史来源，不把未执行的现场或交叉编译检查记成通过。
