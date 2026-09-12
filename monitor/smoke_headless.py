"""Launch the purchase browser headlessly and click a local test page."""
from pathlib import Path
import os
import tempfile
import threading

from playwright.sync_api import sync_playwright

from app import Engine, Handler, ThreadingHTTPServer
from purchase import launch_browser


def main():
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
        engine = Engine(directory)
        engine.add({'locale': 'zh_CN', 'store': 'R390', 'part': 'TEST1CH/A', 'name': '测试商品'})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.engine = engine
        server.token = 'headless-smoke'
        threading.Thread(target=server.serve_forever, daemon=True).start()
        context = launch_browser(pw, Path(directory), 'headless')
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_content('<button id="test" onclick="this.textContent=\'clicked\'">ready</button>')
            page.locator('#test').click()
            assert page.locator('#test').inner_text() == 'clicked'
            page.goto(f'http://127.0.0.1:{server.server_port}/#headless-smoke')
            page.get_by_text('本地服务已连接', exact=False).wait_for()
            assert page.get_by_text('后台加购 · 优先', exact=True).count() == 1
            if os.getenv('STOCKROOM_CONTAINER') == '1':
                visible = page.get_by_text('可见助手 · 原生版', exact=True)
                assert visible.count() == 1 and visible.is_disabled()
            else:
                assert page.get_by_text('可见助手 ↗', exact=True).count() == 1
            print('real headless browser and dual-mode UI: passed')
        finally:
            context.close()
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
