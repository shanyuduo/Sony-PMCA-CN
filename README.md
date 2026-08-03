# Sony-PMCA-CN | 索尼数码相机逆向工程工具（中文版）

本工具通过 USB 与索尼数码相机进行通信，支持调整相机设置、导出固件，以及在部分机型上安装自定义 Android 应用。

本仓库是 [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) 的中文本地化 fork，对所有用户可见的界面文本、命令行帮助、错误提示等信息进行了完整汉化，并提供预编译的 Windows 可执行文件。

> **致谢**：本项目原作者为 [**ma1co**](https://github.com/ma1co)，原始仓库位于 [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)。感谢 ma1co 对索尼相机逆向工程的杰出贡献。

## 下载

前往 [Releases 页面](https://github.com/shanyuduo/Sony-PMCA-CN/releases/latest) 下载最新版本：

| 文件 | 说明 | 平台 |
|------|------|------|
| `pmca-gui-cn-win.exe` | 图形界面程序（完整汉化） | Windows 64 位 |
| `pmca-console-cn-win.exe` | 命令行程序（完整汉化） | Windows 64 位 |

macOS 版本需在 macOS 环境下自行编译，详见下方[编译说明](#从源码编译)。

## 安装

### Windows

下载上方可执行文件即可直接运行，无需安装 Python 或任何依赖。

在 Windows 上使用系统自带的海量存储和 MTP USB 驱动即可正常运行。

### macOS

同样提供 macOS 版本，但测试不如 Windows 版充分。USB 驱动可能需要额外调试。若要以海量存储模式与相机通信，需安装索尼官方的 [Camera Driver](https://support.d-imaging.sony.co.jp/mac/driver/11/ja/)。请确保关闭所有可能访问 USB 驱动的应用程序，包括 Photos、Dropbox 和 Google Drive。

### Linux

本程序基于 Python 3，在 Linux 上使用 libusb 驱动即可运行。

克隆或下载本仓库后，执行以下命令：
```bash
pip install -r requirements.txt  # 安装依赖
./pmca-console.py  # 运行命令行程序
./pmca-gui.py  # 运行图形界面程序
```

## 使用方法

与相机通信主要有三种模式：

### 应用安装器

如果相机支持 *PlayMemories Camera Apps (PMCA)*，可通过本工具安装自定义 Android 应用。支持的相机列表请参见[兼容设备列表](docs/devices.md)。

推荐安装 [*OpenMemories: Tweak*](https://github.com/ma1co/OpenMemories-Tweak) 应用。该应用允许调整相机设置，并启动 *telnet* 和 *adb* 服务以在系统上执行代码。

其他可用应用列表请参见[这里](https://github.com/ma1co/OpenMemories-AppList)。

安装应用有两种方式：
- **图形界面**：在「安装应用」标签页中，从列表选择应用并点击「安装所选应用」。
- **命令行**：运行 `pmca-console install -i` 交互式选择要安装的应用。

### 固件更新模式

索尼相机可从备用分区启动以进行固件更新。利用自定义固件文件，可以在此模式下执行自定义代码。注意：相机固件本身不会被修改，固件更新过程仅用于执行自定义代码。

此模式无需特殊驱动，系统自带的海量存储 USB 驱动即可。

支持的相机型号列表请参见[兼容设备列表](docs/devices.md)。基于 CXD90045 和 CXD90057 架构的设备不兼容，因为其固件经过加密签名。

使用方式有两种：
- **图形界面**：在「高级设置」标签页中，点击「开始调整（固件更新模式）」，然后使用复选框配置相机设置。
- **命令行**：运行 `pmca-console updatershell`。可用命令包括导出固件、执行 Linux 命令以及调整设置。

注意：此操作需要将相机重启至固件更新模式。程序会引导您完成此过程。

### 服务模式

索尼相机有一种名为 *senser mode* 的 USB 模式，用于维修时的校准等操作，也可用于在运行中的系统上执行代码。

服务模式具有最佳的相机兼容性，但需要自定义 USB 驱动。

目前仅命令行程序支持此模式：
- **命令行**：运行 `pmca-console serviceshell`。可用命令包括导出固件和执行 Linux 命令。

#### Windows 驱动安装

在 Windows 上使用服务模式，需通过 [Zadig](http://zadig.akeo.ie/) 安装自定义驱动：
- 确保相机已以海量存储模式连接。
- 在 Zadig 中，勾选 *Options -> List All Devices*，选择相机，选择 *libusb-win32* 并点击 *Replace Driver*。
- 运行 `pmca-console serviceshell` 使相机切换模式。
- 相机切换后，重复上述步骤为服务模式安装驱动。
- 之后即可使用 `pmca-console serviceshell`。

如需恢复正常使用相机，需在设备管理器中卸载 libusb 驱动。

## 从源码编译

### 前置要求

- Python 3.10+（需包含 tkinter）
- pip

### 编译步骤

```bash
# 克隆仓库
git clone https://github.com/shanyuduo/Sony-PMCA-CN.git
cd Sony-PMCA-CN

# 安装依赖
pip install -r requirements.txt

# 编译命令行版本
python -m PyInstaller pmca-console.spec --noconfirm

# 编译图形界面版本
python -m PyInstaller pmca-gui.spec --noconfirm
```

编译产物位于 `dist/` 目录下：
- Windows：`pmca-console-cn-win.exe`、`pmca-gui-cn-win.exe`
- macOS：`pmca-console-cn-osx`、`pmca-gui-cn-osx.dmg`

### macOS 编译说明

macOS 版本需在 macOS 环境下编译，无法在 Windows 上交叉编译。步骤如下：

```bash
# 安装依赖
pip install -r requirements.txt

# 编译
python -m PyInstaller pmca-console.spec --noconfirm
python -m PyInstaller pmca-gui.spec --noconfirm
```

GUI 版本会自动生成 `.app` 包和 `.dmg` 安装镜像。

## 汉化说明

本仓库对以下内容进行了完整汉化：
- 图形界面（GUI）所有按钮、标签、对话框文本
- 命令行帮助信息和参数说明
- 交互式 Shell 提示和命令描述
- USB 设备通信状态消息
- 错误提示和警告信息
- 固件更新流程提示

代码逻辑未做任何修改，仅翻译用户可见的字符串。

## 安全性说明

本项目仍处于非常早期的实验阶段。所有信息均通过逆向工程获得。虽然开发者在测试中一切正常，但仍可能对硬件造成损害。如果损坏了您的相机，后果自负。**我们不承担任何责任。**

## 开发自定义应用

可以为支持的相机开发自定义 Android 应用。请注意，这些应用需要兼容 Android 2.3.7。相机接受调试和发布证书。示例应用请参见 [*PMCADemo*](https://github.com/ma1co/PMCADemo)。

索尼提供了一些特殊 API，可用于发挥相机的各项功能，可通过 [*OpenMemories: Framework*](https://github.com/ma1co/OpenMemories-Framework) 使用。

## 特别感谢

- 原作者 [**ma1co**](https://github.com/ma1co) — 没有你的开创性工作，就没有这个项目
- [nex-hack](http://www.personal-view.com/faqs/sony-hack/hack-development) 社区 — 逆向工程的基础研究

## 许可证

本项目遵循原始仓库的许可证，详见 [LICENSE.txt](LICENSE.txt)。
