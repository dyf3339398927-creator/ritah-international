"""Generate deterministic documentation screenshots without contacting Apple."""
import collections
from pathlib import Path
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

from app import Engine, Handler, ThreadingHTTPServer


class DemoPurchase:
    def snapshot(self):
        return {
            'status': 'bag_confirmed',
            'mode': 'headless',
            'message': '后台加购完成，购物袋中发现目标 SKU；请在官网核对数量、门店并完成付款',
        }


def seed(engine):
    products = [
        {'part': 'DEMO1ZP/A', 'name': '演示 · iPhone 18 Pro 256GB 深绿色', 'locale': 'zh_HK'},
        {'part': 'DEMO2ZP/A', 'name': '演示 · iPhone 18 Pro 512GB 银色', 'locale': 'zh_HK'},
        {'part': 'DEMO3ZP/A', 'name': '演示 · iPhone 18 256GB 蓝色', 'locale': 'zh_HK'},
    ]
    engine.catalogs['zh_HK'] = {
        'products': products,
        'fetchedAt': time.time(),
        'source': 'documentation-demo',
        'warnings': [],
    }
    targets = [
        engine.add({'locale': 'zh_HK', 'store': 'R428', **products[0]}),
        engine.add({'locale': 'zh_HK', 'store': 'R673', **products[1]}),
        engine.add({'locale': 'zh_HK', 'store': 'R610', **products[2]}),
    ]
    now = time.time()
    targets[0].update(status='in_stock', detail='今日可取货（演示状态）', checkedAt=now)
    targets[1].update(status='out_of_stock', detail='目前不可取货（演示状态）', checkedAt=now)
    targets[2].update(status='unknown', reason='官网响应暂时无法确认（演示状态）', checkedAt=now)
    engine.running = True
    engine.next_check = now + 24
    engine.purchase = DemoPurchase()
    engine.logs = collections.deque([
        {'time': now, 'text': '后台加购完成：演示商品（未访问 Apple）', 'kind': 'stock'},
        {'time': now - 8, 'text': 'ifc mall / 演示商品 → in_stock', 'kind': 'stock'},
        {'time': now - 35, 'text': '监控已启动', 'kind': 'info'},
    ], maxlen=200)


def main():
    output = Path(__file__).resolve().parent / 'docs' / 'screenshots'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        engine = Engine(directory)
        seed(engine)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.engine = engine
        server.token = 'documentation-screenshot'
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
                page.goto(f'http://127.0.0.1:{server.server_port}/#documentation-screenshot')
                page.get_by_text('本地服务已连接', exact=False).wait_for()
                page.screenshot(path=str(output / 'workbench-overview.png'), full_page=True)
                page.locator('.targets').screenshot(path=str(output / 'purchase-options.png'))
                page.locator('.log-panel').screenshot(path=str(output / 'background-result.png'))
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print(f'documentation screenshots written to {output}')


if __name__ == '__main__':
    main()
