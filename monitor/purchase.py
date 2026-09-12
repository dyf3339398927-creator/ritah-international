"""User-started shopping-bag helper with an isolated browser session."""
import json
import queue
import threading
import time
from core import product_url, base

MODES = {'visible', 'headless'}

def normalize_mode(value):
    mode = value or 'headless'
    if mode not in MODES:
        raise ValueError('购买助手模式无效')
    return mode

def launch_browser(pw, profile, mode='headless'):
    mode = normalize_mode(mode)
    for channel in ('msedge', 'chrome', None):
        try:
            options = {'channel': channel} if channel else {}
            return pw.chromium.launch_persistent_context(
                str(profile), headless=mode == 'headless', **options)
        except Exception:
            continue
    raise RuntimeError('无法启动购买浏览器；请安装 Edge/Chrome 或执行 playwright install chromium')

class PurchaseWorker:
    def __init__(self, profile):
        self.profile = profile
        self.jobs = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.state = {'status': 'idle', 'message': '后台加购为默认方式；需要人工处理时使用可见助手'}
        self.busy = False
        threading.Thread(target=self.run, daemon=True).start()

    def submit(self, target, mode='headless'):
        mode = normalize_mode(mode)
        with self.lock:
            if self.busy:
                raise ValueError('已有购买任务，请先等待完成或关闭可见窗口')
            label = '后台浏览器' if mode == 'headless' else '购买窗口'
            self.state = {'status': 'queued', 'message': '正在启动' + label,
                          'target': target['id'], 'mode': mode}
            self.busy = True
            self.jobs.put_nowait((dict(target), mode))

    def update(self, status, message):
        with self.lock:
            self.state.update(status=status, message=message)

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def run(self):
        while True:
            target, mode = self.jobs.get()
            try:
                from playwright.sync_api import sync_playwright
                self.update('opening', '启动独立后台浏览器' if mode == 'headless' else '启动独立购买浏览器窗口')
                with sync_playwright() as pw:
                    context = launch_browser(pw, self.profile, mode)
                    try:
                        page = context.pages[0] if context.pages else context.new_page()
                        page.goto(product_url(target['locale'], target['part']), wait_until='domcontentloaded', timeout=45000)
                        if mode == 'visible':
                            self.update('ready', '请在购买窗口确认型号、容量、颜色及服务选项，再按本页悬浮按钮加购')
                            # A local overlay requires the user to review options before a single add click.
                            page.evaluate('''(title) => {
                              const box=document.createElement('div');
                              Object.assign(box.style,{position:'fixed',bottom:'24px',right:'24px',zIndex:2147483647,
                                padding:'20px',background:'#102c24',color:'white',borderRadius:'16px',maxWidth:'330px',font:'14px sans-serif'});
                              const text=document.createElement('p');text.textContent='目标：'+title+'。确认此页面选项后继续。';box.append(text);
                              const btn=document.createElement('button');btn.textContent='我已确认选项 · 加入购物袋';
                              btn.onclick=()=>{window.__pickupConfirmed=true;btn.disabled=true;btn.textContent='正在处理…'};
                              box.append(btn);document.body.append(box);
                            }''', target['name'] + ' / ' + target['part'])
                            while not page.is_closed():
                                if page.evaluate('Boolean(window.__pickupConfirmed)'):
                                    break
                                page.wait_for_timeout(750)
                            if page.is_closed():
                                self.update('closed', '购买窗口已关闭')
                                continue
                        else:
                            self.update('ready', '后台页面已载入，正在核对目标 SKU')
                        self.update('adding', '尝试加入购物袋，仅执行一次')
                        # Require exact SKU evidence in the live page; never substitute another model.
                        content = page.content()
                        if target['part'] not in content and target['part'].split('/')[0] not in page.url:
                            raise ValueError('页面未确认目标 SKU，请手动核对商品')
                        button = page.locator("button[name='add-to-cart']")
                        if button.count() != 1 or not button.is_enabled():
                            raise ValueError('加购按钮不可用，请完成页面选项后手动操作')
                        button.click(timeout=8000)
                        page.wait_for_timeout(2000)
                        page.goto(base(target['locale']) + '/shop/bag', wait_until='domcontentloaded', timeout=30000)
                        body = page.locator('body').inner_text()
                        if target['part'].split('/')[0] in body:
                            message = '购物袋中发现目标 SKU，请核对数量、门店并完成付款'
                            if mode == 'headless':
                                message = '后台加购完成，购物袋中发现目标 SKU；请在官网核对数量、门店并完成付款'
                            self.update('bag_confirmed', message)
                        else:
                            message = '已尝试加购；无法确认购物袋 SKU，请在购买窗口核对。未宣称下单成功'
                            if mode == 'headless':
                                message = '后台已尝试加购，但无法确认购物袋 SKU；请改用可见助手核对。未宣称下单成功'
                            self.update('needs_review', message)
                        if mode == 'visible':
                            while context.pages:
                                try:
                                    context.pages[0].wait_for_timeout(1000)
                                except Exception:
                                    break
                    finally:
                        context.close()
            except ImportError:
                self.update('error', '缺少 Playwright：请安装 requirements.txt 中的依赖')
            except Exception as exc:
                self.update('error', '购买助手未完成：' + str(exc).splitlines()[0][:160])
            finally:
                with self.lock:
                    self.busy = False
                self.jobs.task_done()
