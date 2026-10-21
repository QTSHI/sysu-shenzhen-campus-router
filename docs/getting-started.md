# 从下载仓库开始，一步步动手

这篇给第一次拿到仓库的人看。前半段在 Windows 上完成：下载文件、跑通工具、用官方锐捷确认墙口可用，再采集一次认证协议头。后半段给准备移植路由器的人：在 Ubuntu 中编译程序，生成服务脚本。

准备一台 Windows 电脑、有线网卡、一根网线和自己的 NetID。编译部分另用 Ubuntu 或 WSL，这篇的步骤用不到启动 U 盘。

**做到最后，你会得到自己的协议判断、两个 ARM 程序和两份服务脚本。** 路由器的完整安装入口还在整理，第七步列出需要补齐的部件。已经配好的路由器怎样接线和日常使用，见[接入过程](shenzhen-campus.md)。

## 第一步：下载并打开仓库

### 方法 A：下载 ZIP，适合第一次使用

1. 打开 [GitHub 仓库](https://github.com/QTSHI/sysu-shenzhen-campus-router)。
2. 点击绿色 **Code → Download ZIP**，下载后右键选择“全部解压”。
3. 打开解压后的文件夹，直到能直接看到 `README.md`、`tools`、`docs`、`stock-service`。
4. 在资源管理器地址栏输入 `powershell`，按回车。在这里打开的窗口会直接位于仓库根目录。

在 PowerShell 输入：

```powershell
Get-ChildItem
```

**你应该看到：** `README.md` 和上面的几个目录。后面的 Windows 命令都在这个位置执行。不要在 ZIP 预览窗口里直接运行文件。

### 方法 B：已经安装 Git

在想存放项目的位置打开 PowerShell：

```powershell
git clone https://github.com/QTSHI/sysu-shenzhen-campus-router.git
Set-Location sysu-shenzhen-campus-router
```

两种方式选一种即可。[GitHub 官方下载说明](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)介绍了 ZIP 与克隆的区别。

## 第二步：先跑通一个本地示例

### 2.1 检查 Python

```powershell
py -3 --version
```

需要 **Python 3.9 或更新版本**。还没安装时，从 [Python 官网](https://www.python.org/downloads/windows/)安装，关闭并重新打开 PowerShell 再试。命令识别问题可查看 [Python 的 Windows 说明](https://docs.python.org/3/using/windows.html)。

如果你的电脑能运行 `python --version`，但没有 `py` 命令，也可以把后文的 `py -3` 换成 `python`。这些工具只用 Python 标准库，无需先执行 `pip install`。

### 2.2 解析仓库自带的示例

```powershell
py -3 tools/eap_metadata.py --validate examples/synthetic.jsonl
```

**你应该看到：**

```json
{"records": 3, "success": 1, "failure": 0, "request_types": [1, 4], "complete_handshake_proven": false}
```

这表示解析器读到了 3 条合成记录，其中有一次 Success。`complete_handshake_proven` 是工具保留的完整握手判断字段，显示 `false` 是正常输出，无需修改。

继续运行两组测试：

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m unittest discover -s stock-service -p "test_*.py" -v
```

**你应该看到：** 第一组 16 个测试、第二组 2 个测试，结尾均为 `OK`。

再试：

```powershell
py -3 tools/site_profile.py --json
```

它读的是仓库自带的深圳现场档案，能看到 `result: interrupted`、24 小时测试未完成等信息。到这里，说明工具已经能在你的电脑运行；还没有测试你的墙口。

本地采集和构建产物会在后面的步骤生成。安装包、账号配置和真实采集文件统一放在仓库外，下面会给出目录命令。

## 第三步：先用电脑把自己的墙口接通

### 3.1 接线和网卡设置

把网线接成：

```text
宿舍墙口 ── 网线 ── 电脑有线网口
```

在 PowerShell 查看物理网卡：

```powershell
Get-NetAdapter -Physical |
    Select-Object Name, InterfaceDescription, InterfaceGuid, Status, LinkSpeed |
    Format-List
```

找到实际插线的有线网卡，记下它的 **Name** 和 **InterfaceGuid**。`Wi-Fi` 是另一张网卡。链路正常时通常显示 `Status: Up`；`1 Gbps` 表示线缆连接速率。

按 `Win + R`，输入 `ncpa.cpl` 回车，打开“网络连接”。按刚才的 Name 找到有线网卡，右键 → 属性 → Internet 协议版本 4（TCP/IPv4），将 **IP 地址和 DNS 均设为自动获取**。记下改动前的设置，便于以后恢复。

### 3.2 用学校锐捷客户端认证

从学校[有线接入页面](https://inc.sysu.edu.cn/service/wired-network-access)取得 Windows 客户端，安装后选择刚才那张有线网卡，用自己的 NetID 登录。

如果该网卡属性中的“身份验证”页启用了 Windows 原生 IEEE 802.1X，使用锐捷时取消这个选项，让锐捷处理认证。学校的[客户端 FAQ](https://inc.sysu.edu.cn/cat/152)说明了两者冲突的问题。

认证后，输入这张网卡的实际名称查看配置：

```powershell
$ethernetName = Read-Host '输入刚才看到的有线网卡 Name'
Get-NetIPConfiguration -InterfaceAlias $ethernetName
```

**这一阶段完成的标志：**

- 锐捷显示认证成功。
- 有线网卡拿到有效 IPv4、默认网关和 DNS，地址不再是 `169.254.*.*`。
- 本机条件允许时，暂时断开 Wi-Fi，仍能打开学校网站和公网网站，随后恢复 Wi-Fi。

若通过远程操作这台电脑，先安排好备用连接再断 Wi-Fi。锐捷失败就按错误排查；锐捷成功但没地址，则先查有线 DHCP。[故障排查](troubleshooting.md)按现象列了下一步。

## 第四步：采集一次自己的认证协议头

这一步仍保持“墙口 → 电脑”。锐捷负责认证，采集器在同一张有线网卡旁听。

### 4.1 准备 Npcap

先保存正在做的工作，安装网络驱动可能短暂中断连接。

从 [Npcap 官网](https://npcap.com/)下载免费版安装器，保存在仓库外。右键文件 → 属性 → 数字签名，确认签名有效、发布者为 **Nmap Software LLC**，再运行图形安装器。

本项目使用 Npcap 自己的 DLL 目录，安装时取消 **WinPcap API-compatible Mode**；采集有线 EAPOL 不需要无线监控模式。若选择了仅允许管理员访问，之后用管理员 PowerShell 采集。选项含义见 [Npcap 用户指南](https://npcap.com/guide/npcap-users-guide.html)。

安装后查询驱动：

```powershell
sc.exe query npcap
```

**你应该看到：** `STATE` 为 `RUNNING`。若是 `STOPPED`，可在管理员 PowerShell 执行 `sc.exe start npcap` 后再查；若系统要求重启，先重启。管理员窗口也要重新进入仓库根目录。

### 4.2 把 GUID 对上

```powershell
py -3 tools/eap_metadata.py --list
```

**你应该看到：** 一组 GUID。这里没有网卡名称，要与第三步 `Get-NetAdapter` 的 `InterfaceGuid` 对照，选实际接墙线的有线网卡，不能按列表顺序猜。

### 4.3 开始 30 秒采集

下面的命令会询问 GUID，并把输出写到你个人目录下的 `campus-net-local`，不会写进仓库：

```powershell
$workDir = Join-Path $env:USERPROFILE 'campus-net-local'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$ethernetGuid = Read-Host '粘贴有线网卡的 InterfaceGuid，可带花括号'
$capturePath = Join-Path $workDir ('eap-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.jsonl')
py -3 tools/eap_metadata.py --interface $ethernetGuid --seconds 30 --output $capturePath
```

命令运行后，终端会安静等待约 30 秒。现在切到现有锐捷窗口，进行一次 **断开 → 认证**，然后等采集结束。账号密码只在锐捷窗口输入。

结束时会显示 `{"records": 数字}`。继续检查这个文件：

```powershell
py -3 tools/eap_metadata.py --validate $capturePath
Get-Content -LiteralPath $capturePath
```

**怎样读结果：**

| 字段 | 数字 | 含义 |
| --- | --- | --- |
| `eap_type` | `1` | Identity 请求/应答类型 |
| `eap_type` | `4` | MD5 类型 |
| `eap_code` | `3` | Success，认证成功 |
| `eap_code` | `4` | Failure，认证失败 |

注意 `eap_type` 和 `eap_code` 是两个不同字段。本次深圳墙口看到了 Identity、MD5 和 Success，后来也用标准 MiniEAP 登录成功。

如果记录是 0 条，先确认程序确实运行、GUID 对应、重连发生在这 30 秒内。若只看到请求，再结合客户端结果判断；这套观察器的发送方向可见性有限。整理后的 Windows 前端目前通过了离线测试，现场流程仍需要读者实际核对。

**做到这里：** 你已经验证自己的电脑直连，并取得一次协议头记录。只想诊断校园接入的读者可以在这里结束。

## 第五步：在 Ubuntu 中编译程序

准备移植路由器时再做这一部分。下面命令在 **Ubuntu 22.04 的 Bash** 中运行，不是在 Windows PowerShell 中运行。

### 5.1 打开 Linux 环境

已有 Ubuntu 的读者直接使用。Windows 读者也可以使用 WSL；尚未安装时，按 [Microsoft 官方步骤](https://learn.microsoft.com/en-us/windows/wsl/install)准备，通常涉及管理员权限和重启。例如选择 Ubuntu 22.04：

```powershell
wsl --install -d Ubuntu-22.04
```

首次打开 Ubuntu 时，按窗口要求设置 Linux 用户名和密码。这个密码用于 Linux 的 `sudo`，与校园账号无关。

回到 Windows 中位于仓库根目录的 PowerShell，执行：

```powershell
wsl -d Ubuntu-22.04
```

这会在当前项目目录中打开 Ubuntu。已有其他发行版时，把名字换成 `wsl --list --verbose` 显示的实际名称。原生 Linux 用户则进入自己下载的仓库目录。

接下来的命令在 Ubuntu 内执行。先准备工具：

```bash
sudo apt update
sudo apt install python3 build-essential patch gcc-arm-linux-gnueabi binutils-arm-linux-gnueabi libc6-dev-armel-cross file
```

确认当前目录：

```bash
pwd
ls
```

**你应该看到：** `pwd` 是项目路径，`ls` 列出 `README.md`、`linux-observer`、`scripts`。如果当前目录不对，输入 `exit` 回到 Windows，重新在仓库根目录启动 WSL。WSL 在这一步用于构建；校园流量采集仍放在 Windows 物理网卡上进行。

### 5.2 先用本机编译器测试观察器

```bash
make -C linux-observer test
make -C linux-observer
linux-observer/build/eapol-observer --help
```

**你应该看到：** 合成测试通过，生成的观察器能打印帮助。这份程序属于当前 Linux 的架构；如果 Ubuntu 跑在 x86 电脑上，它就不是路由器的 ARM 程序。

### 5.3 另编一份 ARM 观察器

```bash
make -C linux-observer OUT=build-arm CC=arm-linux-gnueabi-gcc CFLAGS='-D_DEFAULT_SOURCE -std=c11 -Os -Wall -Wextra -Werror -march=armv7-a -mfloat-abi=soft -static'
file linux-observer/build-arm/eapol-observer
arm-linux-gnueabi-readelf -h linux-observer/build-arm/eapol-observer
```

**你应该看到：** ARM、32 位、小端、EABI5、静态链接，与目标 RD03v2 的 ABI 匹配；ELF flags 应为 soft-float，而非 hard-float。ARM 程序留给目标设备使用，前面的测试则用本机编译器运行。

### 5.4 构建 MiniEAP

```bash
python3 scripts/prepare_minieap.py --prepare
sh scripts/build_minieap.sh
file build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294/minieap
arm-linux-gnueabi-readelf -h build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294/minieap
```

第一条需要联网下载固定版本源码，会核对摘要并应用补丁；第二条编译为 ARMv7 soft-float 静态程序。`file` 和 `readelf` 的检查目标与上一小节一致。

如果已经下载了 `third_party/minieap-source.json` 指定的源码 ZIP，可以在准备命令中加 `--archive /实际路径/source.zip`。如果提示目标目录已存在，先查看原构建结果；不要反复执行准备步骤。

**做到这里：** 你有了两个面向 ARM 路由器的程序：

```text
linux-observer/build-arm/eapol-observer
build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294/minieap
```

## 第六步：生成服务脚本

仍在 Ubuntu 的仓库根目录执行。先计算两个程序的真实摘要：

```bash
MINIEAP=build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294/minieap
OBSERVER=linux-observer/build-arm/eapol-observer
MINI_SHA=$(sha256sum "$MINIEAP" | cut -d' ' -f1)
OBS_SHA=$(sha256sum "$OBSERVER" | cut -d' ' -f1)
OUTPUT_DIR=$(mktemp -d "$HOME/campus-net-scripts.XXXXXX")
```

然后生成两份脚本：

```bash
python3 stock-service/render_runner.py --render --artifact runner --minieap-sha256 "$MINI_SHA" --observer-sha256 "$OBS_SHA" --output "$OUTPUT_DIR/runner.sh"
python3 stock-service/render_runner.py --render --artifact shutdown --minieap-sha256 "$MINI_SHA" --observer-sha256 "$OBS_SHA" --output "$OUTPUT_DIR/shutdown.sh"
sh -n "$OUTPUT_DIR/runner.sh"
sh -n "$OUTPUT_DIR/shutdown.sh"
printf '%s\n' "$OUTPUT_DIR"
```

**你应该看到：** 生成器返回 `artifact`、`bytes`、`sha256`；两次 `sh -n` 正常结束且没有语法错误。最后一行打印脚本保存目录。

这里生成的是 shell 源码。它们还会调用设备专属程序，第七步列出这些依赖。

## 第七步：从这些文件到路由器安装，还差什么

当前服务按本次 **RD03v2 / 原厂 2.0.28 / WAN 为 `eth0.1`** 编写。要装到另一台设备，需要补齐下面这段工作：

| 环节 | 要做什么 | 当前仓库提供什么 |
| --- | --- | --- |
| 管理和恢复 | 取得自己的设备管理权限，备份配置，确认回退方法 | 有现场过程，通用操作步骤待整理 |
| 设备检查 | 检查硬件、端口、WAN/LAN 分离和进程归属 | 服务调用 `gate.lua`，该组件待整理 |
| 正常注销 | 准备 `logoff-once`，让它与服务固定的 `LOGOFF_SHA` 对应 | 暂未提供源码或匹配产物 |
| 凭据和配置 | 在本机填写账号，创建受限配置及所需文件 seal | 有非秘密模板，录入和安装流程待整理 |
| 启动和关机 | 放置文件、设置权限，安装启用标记和原厂开关机入口 | 有 runner/shutdown 源码，通用安装器待整理 |

所以目前照教程能完成的是 **线路诊断 → 程序构建 → 服务源码生成**。这一步的缺口会实际影响安装，不能靠上传两个 `.sh` 文件解决；也不应通过删掉校验调用来凑成能运行的脚本。

如果你要继续移植，先看[服务说明](../stock-service/README.md)和[运行流程](architecture.md)，完成这些配套部件后，再安排路由器认证与联网测试。账号配置留在设备受限目录，父目录 `0700`、文件 `0600`。

## 第八步：部署完成后，怎么接线和验收

有完整安装环境之后，日常拓扑是：

```text
宿舍墙口 ── 路由器 WAN
                   └── 自己的 Wi-Fi / LAN ── 手机、电脑
```

只有一根线时，先用它连接电脑和路由器 LAN，完成配置并试通私人 Wi-Fi 管理；再改为墙口到 WAN，电脑转用 Wi-Fi。本次固定后的设备是背面最左口为 WAN、最右口为 LAN，其他设备按实际配置确认。

验收按这个顺序：

1. 看 MiniEAP 本次认证是否 Success。
2. 看校园 WAN 是否取得 IP、网关和 DNS。
3. 电脑连接路由器 Wi-Fi，断开其他联网路径后访问学校和公网网站。
4. 手机连接相同 Wi-Fi，关闭移动数据后访问网站。
5. 普通重启后再做一次上述检查，再分别测试断电上电、拔插 WAN、多设备和长时间使用。

本次实际结果放在[现场记录](field-results.md)。平时排障看[故障排查](troubleshooting.md)，无线、延迟和网速的改善看[网络体验](network-experience.md)。

## 常见卡点

| 现象 | 处理 |
| --- | --- |
| 提示找不到 `tools/eap_metadata.py` | 回到包含 `README.md` 的仓库根目录，通常是少进了一层解压目录 |
| `py` 或 `python` 找不到 | 安装 Python 后重新开终端，确认 `--version` 正常 |
| 采集程序统一提示 `Operation stopped` | 先查 Npcap 驱动、安装架构、管理员权限、GUID 和输出文件是否已存在 |
| 有记录，但没 Success | 对照锐捷窗口；先查本次重连是否成功，再看接口和采集时段 |
| `arm-linux-gnueabi-gcc` 找不到 | 在 Ubuntu 安装交叉编译器，别把构建命令放到 PowerShell |
| `Reviewed renderer source changed` | 从当前 GitHub ZIP 或新克隆重新取一份源码；四层 renderer 的原字节摘要需要匹配 |
| `runner.sh` 生成成功，却无法安装 | 查看第七步的依赖表；目前安装器仍待补齐 |

报问题时附上操作系统、执行到哪一步、命令和脱敏错误即可，账号密码留在本机。
