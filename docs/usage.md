# 工具使用与构建

第一次使用可先看[从下载仓库开始的实操教程](getting-started.md)，这里保留各工具的参数与构建说明。

在仓库根目录运行以下命令。Python 工具需要 **Python 3.9+**，无需安装第三方 Python 包；Windows 采集另外依赖 Npcap，Linux 构建需要编译工具链。

## 先跑一个示例

```sh
python tools/eap_metadata.py --validate examples/synthetic.jsonl
python tools/site_profile.py --json
```

第一条检查合成的认证协议头示例；第二条检查 `profiles/sysu-shenzhen-rd03v2.json` 的字段和结论是否一致。后者不会访问路由器，适合阅读本次实测记录时对照使用。

运行项目已有测试：

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s stock-service -p "test_*.py" -v
```

## Windows：采集认证协议头

这个工具用来回答“墙口发来了哪种 EAP 请求、认证有没有返回 Success”。它与官方锐捷客户端配合：锐捷负责认证，工具只在旁边观察。

1. 从 [Npcap 官网](https://npcap.com/)下载安装器，确认数字签名有效、发布者为 **Nmap Software LLC**，再用图形安装器安装。
2. 先列出接口：

   ```sh
   python tools/eap_metadata.py --list
   ```

3. 找到实际接墙线的物理有线网卡，记下它的 GUID。把下面的 `ADAPTER_GUID` 换成这个值：

   ```sh
   python tools/eap_metadata.py --interface ADAPTER_GUID --seconds 30 --output local-capture.jsonl
   ```

4. 在这 30 秒内，让现有锐捷客户端进行一次“断开 → 认证”。密码只在锐捷窗口输入。采集结束后查看生成的 JSONL。

输出包含 EAPOL/EAP 的类型、长度、编号等 11 个头部字段，方向标为 `unknown`。内核过滤 EAPOL，程序最多读 32 字节前缀以处理两层 VLAN；账号和认证正文不会写入输出。文件名要用新的，工具会拒绝覆盖已有文件。完整依赖说明见 [Npcap 开发文档](https://npcap.com/guide/npcap-devguide.html)。

接口选择很重要：电脑接路由器 LAN 时，看到的是 LAN 流量，观察校园认证要选实际参与认证的那一侧。`--list` 显示的 Ethernet 类型也可能是虚拟接口，应结合 Windows 网卡名称核对。整理后的 Windows 前端目前通过了离线测试，尚未重做现场采集测试。

## Linux：构建协议头观察器

在 Linux 下执行：

```sh
make -C linux-observer test
make -C linux-observer
linux-observer/build/eapol-observer --help
```

产物是 `linux-observer/build/eapol-observer`。先看帮助，再指定自己的接口和观察时间；采集需要相应权限。

观察器只读取 23 字节前缀，保存头部元数据。在本次 ARM/Linux 环境中，它能看到服务器发来的请求；发送方向的可见性还没确认，所以只有接收记录也不表示客户端没有应答。这个版本不解析 VLAN 标签。

实现中还处理了 Linux 4.4 的包地址长度差异：返回长度可能是 18 字节，而结构体占 20 字节。相关说明见[运行流程](architecture.md)。

## 构建本次使用的 MiniEAP

这部分在 Linux 中进行，需要 `patch`、`make` 和 **`arm-linux-gnueabi-gcc`**。构建脚本默认使用这个交叉编译器；通过 `CC` 可以指定另一个兼容工具链。

```sh
python scripts/prepare_minieap.py --prepare
sh scripts/build_minieap.sh
```

第一步下载固定提交的源码，核对摘要并应用本地补丁；第二步编译。产物路径为：

```text
build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294/minieap
```

已有对应源码 ZIP 时，可在准备步骤加 `--archive PATH_TO_ZIP`，避免重新下载。准备目录已存在时脚本会停止，此时先查看里面的内容。

这套构建面向本次 RD03v2 的 **ARMv7 / soft-float / 静态链接** 环境，只启用 `if_impl_sockraw`，关闭 `rjv3`、debug/printer 和额外字符集功能。源码版本及摘要在 [`third_party/minieap-source.json`](../third_party/minieap-source.json)。部署到自己的设备前，需要检查产物的 ELF、ABI 和依赖是否与目标匹配。

## 从构建走到部署

MiniEAP 编译完成后，下一步是填写配置、放置程序并接入原厂启动流程。配置模板在 [`templates/minieap.public.conf.in`](../templates/minieap.public.conf.in)，服务代码在 [`stock-service/`](../stock-service/README.md)。

这一段还没有通用安装器：服务依赖的 `gate.lua`、Logoff 工具、文件摘要及启动配置，需要结合目标设备补齐。具体缺哪些、生成器怎样使用，见[服务说明](../stock-service/README.md)。

账号和密码留在设备上的受限配置文件中，目录权限 `0700`、文件权限 `0600`。分享排障结果时使用脱敏信息，本地采集结果和私人配置不要提交到 Git。
