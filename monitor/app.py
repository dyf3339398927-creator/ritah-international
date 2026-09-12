"""Double-clickable local iPhone monitor; Python 3.10+ standard-library server."""
import argparse
import collections
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

from core import AppleClient, PART, REGIONS, product_url
from purchase import PurchaseWorker

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'web'
STORES = ROOT / 'stores.json'
if not STORES.exists():
    STORES = ROOT.parent / 'config/files/stores.json'

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

class Engine:
    def __init__(self, directory, client=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client = client or AppleClient()
        self.lock = threading.RLock()
        self.query_lock = threading.Lock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.targets = []
        self.interval = 30
        self.running = False
        self.checking = False
        self.revision = 0
        self.next_check = None
        self.backoff = 30
        self.logs = collections.deque(maxlen=200)
        self.catalogs = {}
        self.catalog_state = {}
        self.purchase = None
        self.store_data = self.load_stores()
        self.load()

    def load_stores(self):
        result = {}
        for region in json.loads(STORES.read_text(encoding='utf-8-sig')):
            rows = []
            for store in region.get('store', []):
                rows.append({'id': store['id'], 'name': store['name'].strip(),
                             'city': store.get('address', {}).get('city') or REGIONS.get(region['locale'], ('',))[0]})
            for state in region.get('state', region.get('states', [])):
                for store in state.get('store', []):
                    rows.append({'id': store['id'], 'name': store['name'].strip(),
                                 'city': store.get('address', {}).get('city') or state['name']})
            result[region['locale']] = list({s['id']: s for s in rows}.values())
        return result

    def log(self, text, kind='info'):
        with self.lock:
            self.logs.appendleft({'time': time.time(), 'text': text, 'kind': kind})

    def validate(self, raw):
        if not isinstance(raw, dict):
            raise ValueError('目标必须是对象')
        locale = raw.get('locale')
        part = str(raw.get('part', '')).strip().upper()
        store = raw.get('store')
        if locale not in REGIONS or not PART.fullmatch(part):
            raise ValueError('地区或 SKU 无效')
        local_parts = {p['part'] for p in self.catalogs.get(locale, {}).get('products', [])}
        foreign_parts = {p['part'] for key, catalog in self.catalogs.items() if key != locale
                         for p in catalog.get('products', [])}
        if part not in local_parts and part in foreign_parts:
            raise ValueError('该 SKU 与地区不匹配，请从所选地区的官网目录重新选择')
        found = next((s for s in self.store_data.get(locale, []) if s['id'] == store), None)
        if not found:
            raise ValueError('请选择当前地区的门店')
        return {'id': f'{locale}:{store}:{part}', 'locale': locale, 'part': part, 'store': store,
                'name': str(raw.get('name') or part)[:160], 'storeName': found['city'] + ' · ' + found['name'],
                'url': product_url(locale, part), 'status': 'waiting', 'reason': '', 'checkedAt': None}

    def load(self):
        try:
            data = json.loads((self.directory / 'config.json').read_text(encoding='utf-8'))
            self.targets = [self.validate(t) for t in data.get('targets', [])][:60]
            self.interval = max(30, min(3600, int(data.get('interval', 30))))
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, KeyError):
            self.log('保存的配置无效，请重新配置；原文件暂未覆盖', 'error')
        for locale in REGIONS:
            try:
                data = json.loads((self.directory / f'catalog-{locale}.json').read_text(encoding='utf-8'))
                if isinstance(data.get('products'), list):
                    self.catalogs[locale] = data
            except (OSError, ValueError, AttributeError):
                pass

    def save(self):
        atomic_json(self.directory / 'config.json', {'targets': self.targets, 'interval': self.interval})

    def add(self, raw):
        target = self.validate(raw)
        with self.lock:
            if any(t['id'] == target['id'] for t in self.targets):
                raise ValueError('该型号和门店已在监控列表中')
            if len(self.targets) >= 60:
                raise ValueError('最多添加 60 个目标')
            self.targets.append(target)
            self.save()
        return target

    def refresh(self, locale):
        if locale not in REGIONS:
            raise ValueError('地区无效')
        with self.lock:
            existing = self.catalog_state.get(locale, {})
            if existing.get('loading'):
                return
            if time.time() - existing.get('started', 0) < 60:
                raise ValueError('请等待 60 秒后再刷新目录')
            self.catalog_state[locale] = {'loading': True, 'started': time.time(), 'error': ''}
        def work():
            try:
                data = self.client.catalog(locale)
                with self.lock:
                    atomic_json(self.directory / f'catalog-{locale}.json', data)
                    self.catalogs[locale] = data
                self.log(f'{REGIONS[locale][0]}目录已更新：{len(data["products"])} 个 SKU')
            except Exception as exc:
                with self.lock:
                    self.catalog_state[locale]['error'] = str(exc)[:200]
                self.log('目录刷新失败，保留旧目录：' + str(exc)[:160], 'error')
            finally:
                with self.lock:
                    self.catalog_state[locale]['loading'] = False
        threading.Thread(target=work, daemon=True).start()

    def cycle(self):
        if not self.query_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                targets = copy.deepcopy(self.targets)
                revision = self.revision
                self.checking = True
            groups = collections.defaultdict(list)
            for t in targets:
                groups[(t['locale'], t['store'])].append(t)
            had_errors = False
            for (locale, store), rows in groups.items():
                if self.stop.is_set() or revision != self.revision:
                    break
                try:
                    result = self.client.pickup(locale, store, [t['part'] for t in rows])
                except Exception as exc:
                    result = {t['part']: {'status': 'unknown', 'reason': str(exc)[:200]} for t in rows}
                with self.lock:
                    if revision != self.revision:
                        break
                    for target in self.targets:
                        if target['id'] not in {t['id'] for t in rows}:
                            continue
                        outcome = result.get(target['part'], {'status': 'unknown', 'reason': '缺少目标型号'})
                        had_errors |= outcome['status'] == 'unknown'
                        old = target['status']
                        target.update(outcome, checkedAt=time.time())
                        if old != target['status']:
                            self.log(f'{target["storeName"]} / {target["name"]} → {target["status"]}',
                                     'stock' if target['status'] == 'in_stock' else 'info')
            with self.lock:
                self.backoff = min(900, max(self.interval, self.backoff * 2)) if had_errors else self.interval
                if had_errors:
                    self.log(f'本轮存在未知状态，下轮间隔 {self.backoff} 秒', 'error')
        finally:
            with self.lock:
                self.checking = False
            self.query_lock.release()

    def loop(self):
        while not self.stop.is_set():
            if not self.running:
                self.wake.wait(1)
                self.wake.clear()
                continue
            self.wake.clear()
            self.cycle()
            with self.lock:
                self.next_check = time.time() + self.backoff if self.running else None
            self.wake.wait(self.backoff)
            self.wake.clear()

    def control(self, running):
        with self.lock:
            if running and not self.targets:
                raise ValueError('请先添加监控目标')
            if self.running == running:
                return
            self.running = running
            self.revision += 1
            self.next_check = None
            self.backoff = self.interval
            self.wake.set()
        self.log('监控已启动' if running else '监控已暂停')

    def snapshot(self):
        container = os.getenv('STOCKROOM_CONTAINER') == '1'
        purchase_modes = ['headless'] if container else ['headless', 'visible']
        with self.lock:
            return copy.deepcopy({'targets': self.targets, 'running': self.running, 'checking': self.checking,
                'interval': self.interval, 'nextCheck': self.next_check, 'logs': list(self.logs),
                'catalogs': self.catalogs, 'catalogState': self.catalog_state,
                'regions': {k: v[0] for k, v in REGIONS.items()}, 'stores': self.store_data,
                'purchaseAvailable': True, 'purchaseModes': purchase_modes,
                'purchaseDefault': 'headless', 'container': container,
                'purchase': self.purchase.snapshot() if self.purchase else {'status': 'idle', 'message': ''}})

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Session capabilities are never written to access logs.

    def reply(self, status, value, content_type='application/json; charset=utf-8'):
        blob = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(blob)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(blob)

    def allowed(self):
        host = f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host') == host and self.headers.get('Origin', 'http://' + host) == 'http://' + host

    def authorized(self):
        return self.allowed() and secrets.compare_digest(self.headers.get('X-Session', ''), self.server.token)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {'error': '仅允许本地访问'})
        path = urlsplit(self.path).path
        if path == '/api/state':
            if not self.authorized():
                return self.reply(403, {'error': '会话已过期，请使用启动窗口中的地址'})
            return self.reply(200, self.server.engine.snapshot())
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            return self.reply(404, {'error': '不存在'})
        name, mime = files[path]
        return self.reply(200, (ASSETS / name).read_bytes(), mime)

    def do_POST(self):
        if not self.authorized():
            return self.reply(403, {'error': '本地会话校验失败'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 32768:
                return self.reply(413, {'error': '请求过大'})
            data = json.loads(self.rfile.read(length) or '{}')
            if not isinstance(data, dict):
                raise ValueError('请求必须是对象')
            engine = self.server.engine
            action = urlsplit(self.path).path
            if action == '/api/targets':
                engine.add(data)
            elif action == '/api/remove':
                with engine.lock:
                    engine.targets = [t for t in engine.targets if t['id'] != data.get('id')]
                    engine.save()
            elif action == '/api/control':
                if not isinstance(data.get('running'), bool):
                    raise ValueError('running 必须是布尔值')
                engine.control(data['running'])
            elif action == '/api/settings':
                interval = int(data.get('interval', 30))
                if interval < 30 or interval > 3600:
                    raise ValueError('查询间隔为 30–3600 秒')
                with engine.lock:
                    engine.interval = interval
                    engine.save()
            elif action == '/api/catalog':
                engine.refresh(data.get('locale'))
            elif action == '/api/purchase':
                mode = data.get('mode', 'headless')
                if os.getenv('STOCKROOM_CONTAINER') == '1' and mode != 'headless':
                    raise ValueError('Docker 仅支持后台加购；可见助手请使用 Mac/Windows 原生版')
                with engine.lock:
                    target = next((dict(t) for t in engine.targets if t['id'] == data.get('id')), None)
                if not target:
                    raise ValueError('目标不存在')
                if engine.purchase is None:
                    engine.purchase = PurchaseWorker(engine.directory / 'edge-profile')
                engine.purchase.submit(target, mode)
            else:
                return self.reply(404, {'error': '不存在'})
            self.reply(200, {'ok': True})
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, {'error': str(exc)[:200]})
        except Exception:
            self.reply(500, {'error': '操作失败，请检查本地文件权限或重新启动'})

def serve(engine, port=0, browser=True, host='127.0.0.1'):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.engine = engine
    server.token = secrets.token_urlsafe(32)
    url = f'http://127.0.0.1:{server.server_port}/#{server.token}'
    print('iPhone 18 Stockroom\n' + url + '\n关闭此窗口即停止后台服务。', flush=True)
    threading.Thread(target=engine.loop, daemon=True).start()
    if browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop.set()
        engine.wake.set()
        server.server_close()

def main():
    if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    parser = argparse.ArgumentParser(description='iPhone 18 库存监控与购买助手')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1')
    parser.add_argument('--no-browser', action='store_true')
    data_root = Path.home() / 'Library/Application Support' if sys.platform == 'darwin' else Path(os.getenv('LOCALAPPDATA', str(Path.home())))
    parser.add_argument('--data-dir', type=Path, default=data_root / 'iPhone18Stockroom')
    parser.add_argument('--once', action='store_true', help='读取配置，查询一次并输出 JSON')
    args = parser.parse_args()
    engine = Engine(args.data_dir)
    if args.once:
        engine.cycle()
        print(json.dumps(engine.snapshot()['targets'], ensure_ascii=False, indent=2))
        return 2 if any(t['status'] == 'unknown' for t in engine.targets) else 0
    serve(engine, args.port, not args.no_browser, args.host)
    return 0

if __name__ == '__main__':
    sys.exit(main())
