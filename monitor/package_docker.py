"""Create a Docker source/launcher archive with no local configuration."""
import hashlib
from pathlib import Path
import zipfile

def main():
    repo = Path(__file__).resolve().parent.parent
    dist = repo / 'dist'
    dist.mkdir(exist_ok=True)
    names = ['Dockerfile','compose.yaml','.dockerignore','DOCKER.md','LICENSE','SOURCES.md',
             'Start-Docker-Mac.command','Start-Docker-Windows.cmd',
             'monitor/app.py','monitor/core.py','monitor/purchase.py','config/files/stores.json']
    names += [p.relative_to(repo).as_posix() for p in (repo/'monitor/web').iterdir() if p.is_file()]
    archive = dist / 'iPhone18Stockroom-docker.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in names:
            info = zipfile.ZipInfo('iPhone18Stockroom-docker/' + name)
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            data = (repo/name).read_bytes()
            if name.endswith('.command'):
                data = data.replace(b'\r\n', b'\n')
            z.writestr(info, data)
    print(archive)
    print(hashlib.sha256(archive.read_bytes()).hexdigest())

if __name__ == '__main__':main()
