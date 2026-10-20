# 使用和构建

## 离线测试

需要 Python 3.9 或更新版本，无 Python 第三方依赖：

```text
python -m unittest discover -s tests -v
python tools/eap_metadata.py --validate examples/synthetic.jsonl
```

示例全部是合成字段，没有现场报文、账号、设备地址或密钥。JSONL 验证器只接受一个连续观察段，拒绝额外字段、重复键、布尔冒整数和未完成行。服务分段日志应分段验证，不能重排为一个虚构握手。

## Windows 被动采集

先阅读 [Npcap 官方开发说明](https://npcap.com/guide/npcap-devguide.html)。另从官网取得匹配架构的 Npcap，核验安装器签名，使用正常安装器；本仓库不附带安装包、驱动或静默安装逻辑。采集工具只查询已经运行的驱动，不请求安装/启动权限。管理员授权与认证密码必须在本机处理。

```text
python tools/eap_metadata.py --list
python tools/eap_metadata.py --interface ADAPTER_GUID --seconds 30 --output local-capture.jsonl
```

`ADAPTER_GUID` 必须替换为本人真实物理有线接口的 GUID。连接路由器 LAN 时，不能据该处观察结果推断路由器 WAN 的认证。Windows 前端只加载系统 Npcap 目录，非混杂模式，内核过滤 EAPOL，读取上限 32 字节以兼容两层 VLAN；内存前缀不落地。输出仅为 11 个头部字段，方向记为 `unknown`，不推断发送方身份。

输出文件必须不存在；工具不覆盖已有文件。不要将本机日志提交到仓库。新整理的前端尚未进行现场采集验收，当前只验证离线解析和边界。

## Linux 被动观察器

```text
make -C linux-observer test
make -C linux-observer
linux-observer/build/eapol-observer --help
```

Linux 实际采集需要已明确选定的本人接口与相应权限。显式 `--interface` 和 `--seconds` 才打开套接字；默认帮助不采集。它只读取 23 字节前缀，不保存 PCAP，不发包、不改混杂模式。原 ARM/Linux 组合中接收方向可见性获实证，发送方向未证实，不能据 TX 为零判断没有应答。该版本不解析 VLAN 标签；若目标需要 VLAN 采集，需另做有界实现和测试。

Linux 4.4 的包地址长度可能为 18 字节而非结构体的 20 字节；实现检查字段边界和声明地址长度，而非固定等于 `sizeof`。这个修复保留了 family、ifindex、protocol 的一致性验证。

## 固定 MiniEAP 源码与补丁

使用固定提交、原始 ZIP 摘要和本地补丁，参见 `third_party/minieap-source.json`。准备工具只下载/校验/展开公开源码及打补丁，不构建、不安装、不运行认证：

```text
python scripts/prepare_minieap.py --prepare
# 可选：--archive PATH_TO_THE_EXACT_UPSTREAM_ZIP
sh scripts/build_minieap.sh
```

需要 `patch`、`make` 和相应交叉编译器。准备目录必须不存在，避免覆盖未知历史；源码放在 Git 忽略的 `build/`。脚本不复制上游演示认证配置。构建只启用 `if_impl_sockraw`，关闭 debug/printer/rjv3 和额外字符集功能，目标是 ARM soft-float 静态程序。匿名现场使用过 GNU ARM 交叉编译器 11.4.0；不同工具链结果不保证字节级相同，必须自行检查 ELF、ABI、动态依赖及设备兼容性。

构建成功不代表可以部署到任何 AX3000T。先核实硬件、ABI、端口、固件和恢复条件。本仓库不提供刷机或开 root 的自动入口。

模板 `templates/minieap.public.conf.in` 没有用户名和密码。本人实际配置应仅在设备受限目录中由本机安全流程生成，父目录 `0700`、文件 `0600`；不要把凭据作为 CLI 参数、环境示例或 CI secret 测试输入。公开模板不能直接进行认证。
