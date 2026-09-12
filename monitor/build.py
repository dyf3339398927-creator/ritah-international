"""Native Windows/macOS portable builds; run on each target OS."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
DIST=REPO/'dist'

def main():
    if sys.platform not in ('win32', 'darwin'):
        raise SystemExit('Build on Windows or macOS; cross-compilation is not supported.')
    target = 'windows-x64' if sys.platform == 'win32' else 'macos-' + platform.machine()
    DIST.mkdir(exist_ok=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
        '--name','iPhone18Stockroom','--distpath',str(DIST),'--workpath',str(REPO/'build'),
        '--specpath',str(REPO/'build'),'--paths',str(ROOT),
        '--add-data',f'{ROOT / "web"}{os.pathsep}web',
        '--add-data',f'{REPO / "config/files/stores.json"}{os.pathsep}.',str(ROOT/'app.py')],check=True)
    package=DIST/'iPhone18Stockroom'
    for name in ('LICENSE','SOURCES.md'):
        shutil.copy2(REPO/name,package/name)
    shutil.copy2(ROOT/'README.md',package/'使用说明.md')
    launcher = ROOT / ('Start-Windows.cmd' if sys.platform == 'win32' else 'Start-Mac.command')
    shutil.copy2(launcher, package / launcher.name)
    if sys.platform == 'darwin':
        (package / launcher.name).chmod(0o755)
    # Explicit source allowlist. Runtime config, Edge profiles and caches never enter the archive.
    source=DIST/'iPhone18Stockroom-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob('*'):
            if p.is_file() and p.suffix in ('.py','.md','.txt','.html','.css','.js','.cmd','.command') and '__pycache__' not in p.parts:
                z.write(p,p.relative_to(REPO))
        for p in (REPO/'LICENSE',REPO/'SOURCES.md',REPO/'config/files/stores.json'):
            z.write(p,p.relative_to(REPO))
    shutil.copy2(source,package/source.name)
    archive=Path(shutil.make_archive(str(DIST/f'iPhone18Stockroom-{target}'),'zip',DIST,package.name))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,archive)}
    (DIST/f'SHA256-{target}.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print(json.dumps(hashes,indent=2))

if __name__=='__main__': main()
