# 贡献与验证

本仓库记录中山大学深圳校区宿舍、AX3000T RD03v2 原厂系统的一次接入实践。提交文档修正、兼容性反馈或诊断工具改动时，请保留设备、系统、校区和测试条件的区别。

## 本地检查

从仓库根目录执行：

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s stock-service -p 'test_*.py' -v
python tools/eap_metadata.py --validate examples/synthetic.jsonl
python tools/site_profile.py --json
```

Linux 观察器及 MiniEAP 构建还需要 Linux/对应交叉编译环境，参见 [工具使用与构建](docs/usage.md) 与 [验证记录](VALIDATION.md)。本地单元测试通过不能证明具体墙口、设备或固件已经接通。

## 提交反馈

- 说明设备型号、固件版本、操作系统和文档步骤；区分预期结果与实际结果。
- 只分享脱敏后的协议头摘要和最小复现步骤。不要提交校园账号、密码、私钥、完整配置、抓包或认证负载。
- 文档中区分实测、推断和待验证项目，保留原有现场记录的测试时长与限制。
- 功能和工具改动附上相关测试结果；只改文档时检查相对链接及命令与源码是否一致。
- 修改发布文件后，同步更新 `SOURCE-MANIFEST.json` 中的文件大小与 SHA256；清单不记录自身。保留历史验证的来源，不把未执行的现场或交叉编译检查记成通过。

第三方来源与许可记录位于 [THIRD_PARTY.md](THIRD_PARTY.md)。安全与敏感信息处理参见 [docs/security.md](docs/security.md)。
