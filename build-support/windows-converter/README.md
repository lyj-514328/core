# Windows Converter Build

[Chinese quick start](README.zh-CN.md)

This directory contains the build workflow for the Windows x64 converter.
Run it from Windows. Configuration uses WSL; compilation uses native MSVC
through Git Bash. The source checkout must be on a Windows drive.

## Entry Points

From the source root in a Windows command prompt:

```bat
build-support\windows-converter\run.cmd doctor
build-support\windows-converter\run.cmd all
```

`all` runs prerequisite checks, configuration, an eight-worker build, manifest
verification/repair, DOCX-to-PDF verification, and ZIP packaging. Each stage
stops on failure. It does not install system tools, change Defender settings,
sync source trees, update submodules, or reset local modifications.

Individual stages are available:

```bat
build-support\windows-converter\run.cmd configure
build-support\windows-converter\run.cmd build
build-support\windows-converter\run.cmd manifests
build-support\windows-converter\run.cmd test
build-support\windows-converter\run.cmd test --input "C:\documents\example.docx"
build-support\windows-converter\run.cmd package
```

For an already configured tree, `build` is incremental. Run `manifests`, `test`,
and `package` afterward to validate and package its output. `package` alone
checks ZIP integrity; it does not replace conversion or manifest verification.
Double-clicking `run.cmd` only runs `doctor`; it never starts a build implicitly.

## Machine Setup

1. Install VS 2022 with x64 C++ build tools, ATL, and the Windows SDK. The tested
   versions are in `toolchain-lock.json`: MSVC 14.44.35207 and SDK 10.0.26100.0.
2. Install Git for Windows, LLVM 20.1.8, Windows Python 3.11 or later, and portable
   Strawberry Perl 5.40.0 including its `c/bin/windres.exe`. Python is a build
   tool only; Python UNO is disabled in the converter.
3. Install WSL with a working default Linux distribution. This build used
   Ubuntu 24.04 with its normal build prerequisites: `build-essential`,
   `autoconf`, `automake`, `libtool`, `pkg-config`, `nasm`, `bison`, `flex`,
   `gperf`, `zip`, `unzip`, `patch`, `gettext`, `xsltproc`, `libxml2-utils`,
   `python3`, `perl`, `libarchive-zip-perl`, and `libfont-ttf-perl`.
4. Place `make.exe` (MSVC GNU Make 4.2.1), `jom.exe`, and `pkgconf-2.4.3.exe`
   in `.local/tools`, or point `tools_dir` to an existing tools directory.
   `toolchain-lock.json` records exact sizes and SHA-256 hashes. The already
   verified binaries are retained in this machine's `.local/tools` directory.
   Preserve these binaries when archiving the build environment; `.local` is
   intentionally excluded from Git. Git Bash's MSYS make is not a substitute.
5. Provide a Windows `pdftotext.exe` with its dependencies. This machine uses
   MiKTeX's executable. It is used for verification only, not shipped in ZIP.
6. Create `settings.local.json` from `settings.example.json`. Set installed tool
   paths and optional cache/output paths. Relative paths resolve against this
   directory, not the current terminal directory. Set `jobs` to 8.
7. Ensure Windows Python is on PATH, or create `local.cmd` containing:

```bat
@set "LO_CONVERTER_PYTHON=C:\Python311\python.exe"
```

`settings.local.json` and `local.cmd` are machine-specific and ignored by Git.
For a non-CP936 Windows compiler installation, set `msvc_output_encoding` to
the compiler diagnostic encoding, such as `CP1252`. The included CP936 wrapper
also accepts UTF-8 lines because child tools can change the diagnostic encoding.

## Source and Dependency Reproduction

The successfully built baseline is commit
`e8fa15e0d632c861c7eb3a147d0dd816e670b466`, plus the six-file fixes described below,
`distro-configs/LibreOfficeWin64Converter.conf`, and this directory.
Commit these together and use that resulting Git commit for reproduction.

On a separate checkout of the resulting commit, initialize its submodules:

```bat
git submodule update --init --recursive
```

This initializes the submodule commits recorded by the checkout; no `sync` or
`--remote` operation is needed. The tested submodule commits are:

| Submodule | Commit |
| --- | --- |
| dictionaries | 32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4 |
| helpcontent2 | 099d2dbd383b6fc748d9aa9ca05ac9f2e9aaaaa2 |
| translations | 55b344fac591ef50b17482debc862955d17ce813 |

Use `git -c core.autocrlf=false clone ...` for a fresh Windows checkout, and
`git config core.autocrlf false` within it. Shell scripts must have LF endings.
Do not reset an existing working tree to normalize its line endings.

Upstream `download.lst` pins the external source dependencies. The build fetches
missing archives into `downloads_dir`; preserving that cache reduces reliance
on upstream availability. `downloads-lock.json` records 109 archive/file hashes
from the successful build cache, including portable Perl and jom archives.
It excludes the abandoned source-copy archive and build logs. It is an audit
snapshot, not a downloader; upstream build rules perform dependency fetching.
Tool binaries from `.local/tools` must be archived separately from that cache.

A different source commit, toolchain, system font set or Windows version can
change output. This workflow targets repeatable builds and conversion behavior,
not bit-for-bit identical binaries or ZIP files.

## Configuration Scope

`distro-configs/LibreOfficeWin64Converter.conf` is the authoritative option list.
The build retains Skia, the Windows rendering/UI core, document layout and locale
data, fonts, Writer/Calc/Impress/Draw/Math, and PDF import/export. Run conversions
with `--headless`. This source revision rejects Windows `--disable-gui`, and its
native drawing backend directly depends on Skia.

Java, Python UNO, CLI/.NET bindings, full ODK, help packs, extra UI translations,
MySpell dictionary packages, database connectivity, online update and selected
extensions are disabled. Only `en-US` UI resources are requested.

These configure options do not imply every related file disappears: the current
instdir still contains about 2 MiB of SDK tools and 8.3 MiB of gallery resources.
Some database support code is needed by unconditional Writer/SVX references.
The packaging step preserves the full instdir and performs no speculative pruning.
Chinese documents need suitable fonts on the destination Windows installation;
the package does not include a complete CJK font set or copy Windows fonts.

## Build Fixes

| File / script | Reason |
| --- | --- |
| `external/harfbuzz/ExternalProject_harfbuzz.mk` | Pass native MSVC INCLUDE and LIB paths to Meson. |
| `solenv/gbuild/platform/com_MSC_defs.mk` | Normalize native MSVC include diagnostics before dependency parsing; leave clang diagnostics unchanged. |
| `solenv/gbuild/platform/filter-showIncludes.awk` | Accept long WORKDIR paths alongside Windows 8.3 source/build paths. |
| `svx/Library_svx.mk`, `svx/Library_svxcore.mk` | Link dbtools required by unconditional references with database connectivity disabled. |
| `sw/Library_sw.mk` | Retain dbtools and dbtree required by Writer UI objects. |
| `environment.sh` | Correct compiler/linker order; remove conflicting INCLUDE and UCRTVersion; set UTF-8 compilation and eight-worker jom. |
| `tools/iconv` | Handle mixed CP936 and UTF-8 compiler diagnostic lines. |

During the successful build, `mt.exe` intermittently reported c101008d because
an EXE was in use. Upstream's second manifest update can fail without failing
the whole make target. The `manifests` stage inspects gbuild-owned installed
executables, including `.com` and `.bin`; it preserves their generated manifest,
merges compatibility/DPI/UTF-8 declarations in one write, retries transient
failures, and extracts the result for verification. Third-party executables
without a corresponding gbuild manifest are left alone. No old log is required.

Configuration includes an EICAR antivirus test. On this machine it was initially
blocked, and the user explicitly authorized a Defender exclusion for the exact
source/build directory. The scripts do not change antivirus settings. On another
machine, review any such block locally; the previous approval is not a blanket
exclusion for other paths. The later EXE file-lock cause was not established.

## Outputs and Validation

The converter remains in `<source>/instdir`. The default script output directory
is `build-support/windows-converter/.local/output`, containing timestamped logs,
isolated conversion profiles/PDFs, `libreoffice-converter-win64.zip`, its SHA-256,
`build-record.json`, including the source commit and working-tree status at packaging time.

Deploy the complete ZIP's `instdir` directory. For example:

```bat
instdir\program\soffice.com --headless --convert-to pdf --outdir C:\output C:\input\example.docx
```

The original eight-worker build completed successfully. Its instdir was about
472 MiB; ZIP was about 167 MiB. The generated smoke document preserved English,
Chinese, and numbers in extracted PDF text. The user's `ComplexDoc.docx` produced
a six-page PDF of 593,557 bytes. That private input is not copied into this folder.
These tests do not establish layout fidelity for every supported document format.

The relocated workflow is verified with environment checks, configuration, manifest inspection,
conversion tests and ZIP integrity checks. A fresh full rebuild is a separate,
long-running verification; do not confuse these checks with a second clean build.
