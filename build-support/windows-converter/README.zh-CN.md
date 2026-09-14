# Windows 文档转换器构建

构建方案和脚本位于本目录，具体配置位于源码根目录的
`distro-configs/LibreOfficeWin64Converter.conf`。
完整的依赖、源码修复和故障说明见 [README.md](README.md)。

## 本机使用

在 **Windows 命令提示符**中进入源码根目录，执行：

```bat
build-support\windows-converter\run.cmd all
```

依次执行：环境检查 → 配置 → 8 线程编译 → manifest 检查/修复 →
中英文 DOCX 转换测试 → ZIP 打包及校验。任何步骤失败即停止。
配置阶段内部调用 WSL，编译由 Git Bash 调用 Windows 原生 MSVC。
双击 `run.cmd` 默认只检查环境。

修改源码后，只需增量构建时：

```bat
build-support\windows-converter\run.cmd build
build-support\windows-converter\run.cmd manifests
build-support\windows-converter\run.cmd test
build-support\windows-converter\run.cmd package
```

额外测试指定文档：

```bat
build-support\windows-converter\run.cmd test --input "C:\Users\LYJ514328\Downloads\ComplexDoc.docx"
```

## 输出位置

- 运行文件：源码根目录 `instdir`，部署时需要整个目录。
- ZIP、SHA-256、构建记录和测试 PDF：本目录 `.local/output`。
- 每次环境检查、配置和编译日志：`.local/output/logs`。
- 原先成功构建的历史日志：`.local/history`。

## 换机器复现

需要安装 VS 2022、Windows SDK、Git for Windows、LLVM、Windows Python、
WSL 和便携 Strawberry Perl；具体版本见 `toolchain-lock.json`。
测试还需要 `pdftotext.exe`，它不随转换器发布。

从 `settings.example.json` 创建 `settings.local.json`，修改工具安装路径。
`local.cmd` 可以指定 Windows Python 路径。源码位置由脚本自身推导，
无需再写死用户名和源码路径。

本机便携 make、jom 和 pkgconf 已归档在 `.local/tools`。
Strawberry Perl 安装和第三方源码下载缓存仍复用 `D:/lo-converter` 下的
现有目录，它们是依赖缓存，不是脚本入口；换机器时可在配置中改到新位置。
`downloads-lock.json` 记录现有下载文件的 SHA-256。

**保存源码时，需要一起保存本目录、distro 配置及六个已修改的源码文件。**
将这些文件一起提交到 Git，后续直接检出该提交并初始化子模块即可准备源码，
无需单独应用 patch。打包时会记录当前提交和工作区状态。

`.local`、`settings.local.json` 和 `local.cmd` 被 Git 忽略。
若要离线复现，需要额外备份便携工具和下载缓存；仅提交脚本不包含这些二进制依赖。
脚本不会同步源码、重置改动或自动修改 Defender 排除项。

## 已验证范围

原先的 8 线程完整编译已成功。迁移后的入口已通过环境检查、配置、29 个
安装程序的 manifest 检查、中英文烟测、`ComplexDoc.docx` 转换，以及 ZIP
完整性检查。此次未再执行一轮从零完整编译。

保留 Skia 和当前字体配置；未新增裁剪。文档转换结果仍受系统字体影响，
工具链和源码版本变化也可能影响产物，因此不承诺二进制逐字节相同。
