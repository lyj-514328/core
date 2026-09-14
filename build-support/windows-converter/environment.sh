#!/usr/bin/env bash
set -euo pipefail

support=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$support/../.."
tools=$(cygpath -u "$LO_CONVERTER_TOOLS")
llvm=$(cygpath -u "$LO_CONVERTER_LLVM")
python=$(cygpath -u "$LO_CONVERTER_PYTHON_EXE")
strawberry=$(cygpath -u "$LO_CONVERTER_STRAWBERRY")
export PATH="$support/tools:$tools:$llvm:/mingw64/bin:/usr/bin:/c/Windows/Sysnative:/c/Windows/System32:/c/Windows:$(dirname -- "$python")"

case "${1:-}" in
    doctor)
        for tool in make.exe perl.exe clang-cl.exe iconv; do
            command -v "$tool"
        done
        make.exe --version | head -1
        wsl.exe --exec sh -c 'for tool in autoconf perl make nasm pkg-config; do command -v "$tool" || exit; done'
        ;;
    configure)
        export WSLENV="${WSLENV:+$WSLENV:}COMSPEC:MSYSTEM"
        exec wsl.exe ./autogen.sh --with-distro=LibreOfficeWin64Converter \
            "--with-strawberry-perl-portable=$LO_CONVERTER_STRAWBERRY" \
            "--with-external-tar=$LO_CONVERTER_DOWNLOADS" \
            "--with-parallelism=$LO_CONVERTER_JOBS" \
            "PYTHON=$(basename -- "$python")" \
            "PKG_CONFIG=$LO_CONVERTER_TOOLS/pkgconf-2.4.3.exe" \
            "LO_CLANG_CC=clang-cl.exe --target=x86_64-pc-windows-msvc -m64" \
            "LO_CLANG_CXX=clang-cl.exe --target=x86_64-pc-windows-msvc -m64" \
            "LO_CLANG_SHOWINCLUDES_PREFIX=Note: including file:"
        ;;
    build)
        compiler_root=$(sed -n 's/^export COMPATH=//p' config_host.mk)
        sdk_root=$(sed -n 's/^export WINDOWS_SDK_HOME=//p' config_host.mk)
        sdk_version=$(sed -n 's/^export WINDOWS_SDK_LIB_SUBDIR=//p' config_host.mk)
        export PATH="$support/tools:$tools:$(cygpath -u "$compiler_root/bin/Hostx64/x64"):$(cygpath -u "$sdk_root/bin/$sdk_version/x64"):$PATH:$strawberry/c/bin"
        export CL="${CL:+$CL }-utf-8"
        # Avoid duplicate MSBuild variables and gbuild's flag-style INCLUDE.
        unset UCRTVersion INCLUDE
        export MSVC_OUTPUT_ENCODING="$LO_CONVERTER_ENCODING"
        exec make.exe "-j$LO_CONVERTER_JOBS" "JOM=$LO_CONVERTER_TOOLS/jom.exe" \
            "PATH=$(cygpath -mp "$PATH")" "SHELL=$(cygpath -ms /usr/bin/sh.exe)" build
        ;;
    *) echo 'Expected doctor, configure or build' >&2; exit 2 ;;
esac
