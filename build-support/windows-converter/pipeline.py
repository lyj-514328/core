"""Windows converter build, verification and packaging entry point."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

SUPPORT = Path(__file__).resolve().parent
SOURCE = SUPPORT.parent.parent


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def settings():
    path = SUPPORT / 'settings.local.json'
    if not path.exists():
        raise RuntimeError('Create settings.local.json from settings.example.json first.')
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    for key in ('git_bash', 'vs_dev_cmd', 'llvm_bin', 'strawberry_root',
                'tools_dir', 'downloads_dir', 'output_dir', 'pdftotext'):
        value = Path(os.path.expandvars(config[key]))
        config[key] = value.resolve() if value.is_absolute() else (SUPPORT / value).resolve()
    if not isinstance(config['jobs'], int) or config['jobs'] < 1:
        raise RuntimeError('jobs must be a positive integer')
    return config


def environment(config):
    # Capture the environment without printing any inherited values or secrets.
    command = f'cmd.exe /d /s /c ""{config["vs_dev_cmd"]}" -arch=x64 -host_arch=x64 >nul && set"'
    result = subprocess.run(command, cwd=SOURCE, check=True, capture_output=True)
    env = dict(os.environ)
    for line in result.stdout.decode('mbcs').splitlines():
        key, separator, value = line.partition('=')
        if separator and key:
            for existing in list(env):
                if existing.casefold() == key.casefold():
                    del env[existing]
            env[key] = value
    env.update({
        'LO_CONVERTER_TOOLS': config['tools_dir'].as_posix(),
        'LO_CONVERTER_LLVM': config['llvm_bin'].as_posix(),
        'LO_CONVERTER_PYTHON_EXE': Path(sys.executable).as_posix(),
        'LO_CONVERTER_STRAWBERRY': config['strawberry_root'].as_posix(),
        'LO_CONVERTER_DOWNLOADS': config['downloads_dir'].as_posix(),
        'LO_CONVERTER_JOBS': str(config['jobs']),
        'LO_CONVERTER_ENCODING': config.get('msvc_output_encoding', 'CP936'),
    })
    return env


def shell(config, env, stage):
    log_dir = config['output_dir'] / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f'{stage}-{time.time_ns()}.log'
    command = [str(config['git_bash']), str(SUPPORT / 'environment.sh'), stage]
    print(f'{stage}: log {log}', flush=True)
    with log.open('wb') as stream:
        with subprocess.Popen(command, cwd=SOURCE, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as process:
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                print(line.decode('utf-8', errors='replace'), end='', flush=True)
            code = process.wait()
    if code:
        raise RuntimeError(f'{stage} failed with exit code {code}; see {log}')


def doctor(config, env):
    paths = [config['git_bash'], config['vs_dev_cmd'], config['pdftotext'],
             config['llvm_bin'] / 'clang-cl.exe',
             config['strawberry_root'] / 'perl/bin/perl.exe',
             config['strawberry_root'] / 'c/bin/windres.exe']
    lock = json.loads((SUPPORT / 'toolchain-lock.json').read_text())
    for item in lock['portable_tools']:
        path = config['tools_dir'] / item['name']
        paths.append(path)
        if path.is_file() and sha256(path) != item['sha256']:
            raise RuntimeError(f'Tool checksum mismatch: {path}')
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f'Required tool not found: {path}')
    config['downloads_dir'].mkdir(parents=True, exist_ok=True)
    shell(config, env, 'doctor')
    print('Prerequisites found; portable tool checksums verified.')


def manifest_tool(env):
    path = shutil.which('mt.exe', path=env.get('PATH', env.get('Path', '')))
    if not path:
        raise RuntimeError('mt.exe not found in the VS developer environment')
    return path


def verify_manifests(config, env):
    mt = manifest_tool(env)
    platform = SOURCE / 'solenv/gbuild/platform'
    fragments = [platform / name for name in (
        'win_compatibility.manifest', 'DeclareDPIAware.manifest', 'UseUtf8.manifest')]
    required = []
    for fragment in fragments:
        for node in ET.parse(fragment).iter():
            if node.tag.rsplit('}', 1)[-1] in ('supportedOS', 'dpiAware', 'activeCodePage'):
                required.append((node.tag, node.attrib, (node.text or '').strip()))

    def complete(path):
        nodes = list(ET.parse(path).iter())
        return all(any(n.tag == tag and n.attrib == attrs and
                       (n.text or '').strip() == value for n in nodes)
                   for tag, attrs, value in required)

    originals = SOURCE / 'workdir/LinkTarget/Executable'
    # Only gbuild-owned executables have these manifest requirements. Third-party
    # helpers can intentionally have no manifest; do not change their metadata.
    targets = sorted(p for p in (SOURCE / 'instdir').rglob('*')
                     if p.is_file() and p.suffix.lower() in ('.exe', '.com', '.bin')
                     and (originals / (p.name + '.manifest')).is_file())
    if not targets or not (SOURCE / 'instdir/program/soffice.exe').is_file():
        raise RuntimeError('No complete build found in instdir')
    repaired = 0
    with tempfile.TemporaryDirectory(prefix='lo-manifests-') as temp:
        extracted = Path(temp) / 'current.xml'
        for target in targets:
            extract = [mt, '-nologo', f'-inputresource:{target.as_posix()};1',
                       f'-out:{extracted.as_posix()}']
            result = subprocess.run(extract, capture_output=True)
            if result.returncode == 0 and complete(extracted):
                continue
            original = originals / (target.name + '.manifest')
            if original.exists():
                base = [original]
            elif result.returncode == 0:
                base = [extracted]
            else:
                raise RuntimeError(f'Cannot preserve original manifest for {target}')
            command = [mt, '-nologo', '-manifest',
                       *[p.as_posix() for p in base + fragments],
                       f'-outputresource:{target.as_posix()};1']
            for attempt in range(5):
                result = subprocess.run(command, capture_output=True, timeout=30)
                if result.returncode == 0:
                    break
                if attempt == 4:
                    raise RuntimeError(f'Manifest update failed: {target}: {result.stdout!r}')
                time.sleep(0.5)
            subprocess.run(extract, check=True, capture_output=True, timeout=30)
            if not complete(extracted):
                raise RuntimeError(f'Manifest verification failed: {target}')
            repaired += 1
    print(f'Manifests verified: {len(targets)}; repaired: {repaired}')


def convert(config, input_file=None):
    from smoke_test import create_document, EXPECTED_TEXT

    config['output_dir'].mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='test-', dir=config['output_dir']))
    if input_file is None:
        input_file = output / 'converter-smoke.docx'
        create_document(input_file)
        expected = EXPECTED_TEXT
    else:
        input_file = input_file.resolve(strict=True)
        expected = []
    subprocess.run([str(SOURCE / 'instdir/program/soffice.com'),
                    '-env:UserInstallation=' + (output / 'profile').as_uri(),
                    '--headless', '--convert-to', 'pdf', '--outdir', str(output),
                    str(input_file)], check=True, timeout=180)
    pdf = output / (input_file.stem + '.pdf')
    if not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-'):
        raise RuntimeError('Conversion did not produce a PDF')
    result = subprocess.run([str(config['pdftotext']), '-enc', 'UTF-8', str(pdf), '-'],
                            check=True, capture_output=True, timeout=60)
    text = result.stdout.decode('utf-8')
    for value in expected:
        if value not in text:
            raise RuntimeError(f'Missing PDF text: {value!a}')
    (output / (input_file.stem + '.txt')).write_text(text, encoding='utf-8')
    print(f'PDF verified: {pdf} ({pdf.stat().st_size} bytes)')


def package(config):
    files = sorted(p for p in (SOURCE / 'instdir').rglob('*') if p.is_file())
    if not files or not (SOURCE / 'instdir/program/soffice.com').exists():
        raise RuntimeError('No complete build found in instdir')
    output = config['output_dir']
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'libreoffice-converter-win64.zip'
    temporary = target.with_suffix('.zip.tmp')
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                archive.write(path, path.relative_to(SOURCE).as_posix())
        with ZipFile(temporary) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f'ZIP integrity failure: {bad}')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    checksum = sha256(target)
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {target.name}\n')
    git = config['git_bash'].parent / 'git.exe'
    head = subprocess.check_output([str(git), 'rev-parse', 'HEAD'], cwd=SOURCE).decode().strip()
    provenance = {
        'source_head': head,
        'source_status': subprocess.check_output(
            [str(git), 'status', '--porcelain'], cwd=SOURCE).decode('utf-8', errors='replace'),
        'config_sha256': sha256(SOURCE / 'distro-configs/LibreOfficeWin64Converter.conf'),
        'toolchain_lock': json.loads((SUPPORT / 'toolchain-lock.json').read_text()),
        'files': len(files), 'uncompressed_bytes': sum(p.stat().st_size for p in files),
        'zip_bytes': target.stat().st_size, 'zip_sha256': checksum,
    }
    (output / 'build-record.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'ZIP verified: {target} ({target.stat().st_size} bytes), SHA256 {checksum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('doctor', 'configure', 'build', 'manifests',
                                         'test', 'package', 'all'), nargs='?', default='doctor')
    parser.add_argument('--input', type=Path, help='Additional document to convert during test')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Run run.cmd in Windows; WSL is called internally for configuration.')
    config = settings()
    needs_vs = args.stage not in ('test', 'package')
    env = environment(config) if needs_vs else None
    stages = ('doctor', 'configure', 'build', 'manifests', 'test', 'package') if args.stage == 'all' else (args.stage,)
    for stage in stages:
        if stage == 'doctor':
            doctor(config, env)
        elif stage in ('configure', 'build'):
            shell(config, env, stage)
        elif stage == 'manifests':
            verify_manifests(config, env)
        elif stage == 'test':
            convert(config)
            if args.input:
                convert(config, args.input)
        elif stage == 'package':
            package(config)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
