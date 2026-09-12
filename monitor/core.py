"""Apple pickup client. GPL-3.0-or-later; see SOURCES.md."""
import html
import gzip
import io
import http.cookiejar
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

REGIONS = {
    'zh_HK': ('中国香港', 'https://www.apple.com/hk-zh'),
    'ja_JP': ('日本', 'https://www.apple.com/jp'),
    'zh_CN': ('中国大陆', 'https://www.apple.com.cn'),
    'zh_TW': ('中国台湾', 'https://www.apple.com/tw'),
    'en_SG': ('新加坡', 'https://www.apple.com/sg'),
    'en_AU': ('澳大利亚', 'https://www.apple.com/au'),
    'en_MY': ('马来西亚', 'https://www.apple.com/my'),
}
PART = re.compile(r'^[A-Z0-9]{5,12}/[A-Z]$')

def base(locale):
    if locale not in REGIONS:
        raise ValueError('不支持的地区')
    return REGIONS[locale][1]

def product_url(locale, part):
    if not PART.fullmatch(part):
        raise ValueError('SKU 格式无效，请从官网目录选择')
    return base(locale) + '/shop/product/' + urllib.parse.quote(part, safe='/')

def clean(value):
    text = html.unescape(re.sub('<[^>]+>', '', str(value)))
    text = re.sub(r'(?:脚注|註腳|Footnote)\s*\d+', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()

def parse_catalog(page, locale, source):
    """Parse only product records; never invent part numbers from model names."""
    matches = list(re.finditer(r'["\']?productSelectionData["\']?\s*:', page))
    products = {}
    for match in matches:
        try:
            data, _ = json.JSONDecoder().raw_decode(page[match.end():].lstrip())
        except (ValueError, TypeError):
            continue
        display = data.get('displayValues') or {}
        for item in data.get('products') or []:
            part = item.get('partNumber', '')
            if not PART.fullmatch(part):
                continue
            def label(key):
                value = item.get(key, '')
                entry = display.get(key, {}).get(value, {})
                return clean(entry.get('value', value)) if isinstance(entry, dict) else clean(value)
            model = label('dimensionScreensize') or clean(item.get('familyType', 'iPhone'))
            title = ' '.join(filter(None, [model, label('dimensionCapacity'), label('dimensionColor')]))
            products[part] = {'part': part, 'name': title, 'locale': locale,
                              'color': label('dimensionColor'), 'capacity': label('dimensionCapacity'),
                              'url': product_url(locale, part), 'source': source}
    return list(products.values())

def parse_pickup(data, store, parts):
    if not isinstance(data, dict):
        raise ValueError('库存响应格式改变')
    body = data.get('body') or {}
    status = (data.get('head') or {}).get('status')
    if status not in (None, 200, '200') or body.get('errorMessage'):
        raise ValueError('Apple 返回业务错误')
    stores = body.get('stores') or body.get('content', {}).get('pickupMessage', {}).get('stores', [])
    found = next((s for s in stores if s.get('storeNumber') == store), None)
    if found is None:
        raise ValueError('响应缺少目标门店，不能判断库存')
    result = {}
    for part in parts:
        entry = found.get('partsAvailability', {}).get(part, {})
        raw = str(entry.get('pickupDisplay', '')).strip().lower()
        state = {'available': 'in_stock', 'unavailable': 'out_of_stock',
                 'ineligible': 'ineligible'}.get(raw, 'unknown')
        if entry.get('partNumber') not in (None, '', part):
            state = 'unknown'
        result[part] = {'status': state, 'detail': clean(entry.get('pickupSearchQuote', ''))[:300],
                        'raw': raw, 'reason': '库存字段缺失或不一致' if state == 'unknown' else ''}
    return result

class AppleClient:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.lock = threading.Lock()
        self.last = 0.0
        self.warmed = set()

    def get(self, url, accept='text/html'):
        # Serialize outbound requests and reuse cookies. Do not rotate proxies or bypass challenges.
        with self.lock:
            time.sleep(max(0, 1.0 - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ApplePickupMonitor/1.0',
                'Accept': accept, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
            try:
                with self.opener.open(req, timeout=15) as response:
                    blob = response.read(4 * 1024 * 1024 + 1)
                    if len(blob) > 4 * 1024 * 1024:
                        raise ValueError('响应超过大小限制')
                    if blob[:2] == b'\x1f\x8b':
                        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as gz:
                            blob = gz.read(4 * 1024 * 1024 + 1)
                        if len(blob) > 4 * 1024 * 1024:
                            raise ValueError('解压响应超过大小限制')
                    return blob.decode('utf-8')
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 541):
                    raise ValueError(f'Apple 拦截请求 HTTP {exc.code}；请稍后再试') from None
                if exc.code == 429:
                    raise ValueError('Apple 限流 HTTP 429；已等待后重试') from None
                raise ValueError(f'Apple HTTP {exc.code}') from None
            except (urllib.error.URLError, TimeoutError):
                raise ValueError('网络连接失败或超时') from None

    def catalog(self, locale):
        root = base(locale) + '/shop/buy-iphone'
        page = self.get(root)
        slugs = sorted(set(re.findall(r'buy-iphone/(iphone-[a-z0-9-]+)', page)))[:12]
        items = {p['part']: p for p in parse_catalog(page, locale, root)}
        errors = []
        for slug in slugs:
            url = root + '/' + slug
            try:
                for p in parse_catalog(self.get(url), locale, url):
                    items[p['part']] = p
            except ValueError as exc:
                errors.append(str(exc))
        if not items:
            raise ValueError('官网目录尚未返回可用 SKU；请稍后刷新。' + ('；'.join(errors[:1])))
        return {'products': sorted(items.values(), key=lambda p: ('18' not in p['name'], p['name'])),
                'fetchedAt': time.time(), 'source': root, 'warnings': errors}

    def pickup(self, locale, store, parts):
        root = base(locale)
        if locale not in self.warmed:
            try:
                self.get(root + '/shop/buy-iphone')
                self.warmed.add(locale)
            except ValueError:
                pass
        query = {'pl': 'true', 'store': store}
        for i, part in enumerate(parts):
            query[f'parts.{i}'] = part
            query[f'mts.{i}'] = 'regular'
        raw = self.get(root + '/shop/retail/pickup-message?' + urllib.parse.urlencode(query), 'application/json')
        try:
            return parse_pickup(json.loads(raw), store, parts)
        except json.JSONDecodeError:
            raise ValueError('返回了网页而非库存 JSON，库存未知') from None
