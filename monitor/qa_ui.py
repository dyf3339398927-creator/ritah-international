"""Read-only live UI smoke test. No shopping-bag or payment action is invoked."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from playwright.sync_api import sync_playwright
from app import Engine, Handler, ThreadingHTTPServer

def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else '../qa')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as data:
        engine=Engine(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.engine=engine;server.token='local-ui-test'
        threading.Thread(target=server.serve_forever,daemon=True).start()
        threading.Thread(target=engine.loop,daemon=True).start()
        errors=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                page.on('pageerror',lambda err:errors.append(str(err)))
                page.goto(f'http://127.0.0.1:{server.server_port}/#local-ui-test')
                page.get_by_text('本地服务已连接',exact=False).wait_for()
                page.screenshot(path=str(output/'desktop-empty.png'),full_page=True)
                page.locator('#refresh').click()
                page.wait_for_function("() => document.querySelector('#product').options.length > 0",timeout=180000)
                options=page.locator('#product option').all_text_contents()
                if not options:
                    page.locator('#filter').fill('')
                    options=page.locator('#product option').all_text_contents()
                page.locator('#addForm button[type=submit]').click()
                page.wait_for_function("() => document.querySelectorAll('.target').length===1")
                page.locator('#toggle').click()
                page.wait_for_function("() => document.querySelector('.target .status').textContent!=='待查询'",timeout=60000)
                page.locator('#toggle').click()
                page.wait_for_function("() => document.querySelector('#runstate').textContent==='已暂停'")
                page.screenshot(path=str(output/'desktop-live.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(output/'mobile-live.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'horizontal overflow'
                assert not errors,errors
                report={'ui':'passed','products':len(options),'liveTarget':engine.snapshot()['targets'],
                        'consoleErrors':errors,'desktop':'1440px','mobile':'390px'}
                (output/'ui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(report,ensure_ascii=True))
                browser.close()
        finally:
            engine.stop.set();engine.wake.set();server.shutdown();server.server_close()

if __name__=='__main__':main()
