import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

from core import parse_pickup, parse_catalog
from app import Engine, Handler, ThreadingHTTPServer
from purchase import launch_browser, normalize_mode

SKU = 'TEST1CH/A'

def response(display='available', store='R390'):
    return {'head': {'status': 200}, 'body': {'stores': [{'storeNumber': store,
        'partsAvailability': {SKU: {'partNumber': SKU, 'pickupDisplay': display}}}]}}

class Fake:
    def __init__(self): self.calls = []; self.error = False
    def pickup(self, locale, store, parts):
        self.calls.append((locale, store, parts))
        if self.error: raise ValueError('HTTP 541')
        return {p: {'status': 'in_stock', 'reason': ''} for p in parts}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = Fake()
        self.engine = Engine(self.tmp.name, self.client)
    def tearDown(self): self.tmp.cleanup()
    def target(self, part=SKU):
        return self.engine.add({'locale':'zh_CN','store':'R390','part':part,'name':'测试商品'})
    def test_states(self):
        for raw, expected in [('available','in_stock'),('unavailable','out_of_stock'),('ineligible','ineligible'),('new','unknown')]:
            self.assertEqual(parse_pickup(response(raw),'R390',[SKU])[SKU]['status'],expected)
    def test_errors_never_become_stock(self):
        for data in [{}, response(store='R999'), {'head':{'status':500},'body':response()['body']}]:
            with self.assertRaises(ValueError): parse_pickup(data,'R390',[SKU])
        data=response();data['body']['stores'][0]['partsAvailability'][SKU]['partNumber']='OTHERCH/A'
        self.assertEqual(parse_pickup(data,'R390',[SKU])[SKU]['status'],'unknown')
    def test_missing_part_unknown(self):
        self.assertEqual(parse_pickup(response(),'R390',['OTHERCH/A'])['OTHERCH/A']['status'],'unknown')
    def test_grouping_failure_and_recovery(self):
        self.target();self.target('TEST2CH/A');self.engine.cycle()
        self.assertEqual(len(self.client.calls),1)
        self.assertEqual(len(self.client.calls[0][2]),2)
        self.client.error=True;self.engine.cycle()
        self.assertTrue(all(t['status']=='unknown' for t in self.engine.targets))
        self.assertEqual(self.engine.backoff,60)
        self.client.error=False;self.engine.cycle();self.assertEqual(self.engine.backoff,30)
    def test_persistence_not_autostart(self):
        self.target();other=Engine(self.tmp.name,self.client)
        self.assertEqual(len(other.targets),1);self.assertFalse(other.running)
        self.assertEqual(other.targets[0]['status'],'waiting')
    def test_duplicate_and_invalid_store(self):
        self.target()
        with self.assertRaises(ValueError): self.target()
        with self.assertRaises(ValueError): self.engine.add({'locale':'zh_HK','store':'R390','part':SKU})
    def test_hk_japan_stores_and_sku_separation(self):
        self.assertEqual(len(self.engine.store_data['zh_HK']),6)
        self.assertGreater(len(self.engine.store_data['ja_JP']),0)
        self.engine.add({'locale':'zh_HK','store':'R428','part':'TEST1ZP/A'})
        self.engine.catalogs['zh_HK']={'products':[{'part':'TEST1ZP/A'}]}
        with self.assertRaises(ValueError):
            self.engine.add({'locale':'ja_JP','store':self.engine.store_data['ja_JP'][0]['id'],'part':'TEST1ZP/A'})
    def test_stop_discards_inflight_results(self):
        self.target()
        def pickup(*args):
            self.engine.revision+=1
            return {SKU:{'status':'in_stock'}}
        self.client.pickup=pickup;self.engine.cycle()
        self.assertEqual(self.engine.targets[0]['status'],'waiting')
    def test_catalog_no_fabricated_sku(self):
        self.assertEqual(parse_catalog('iPhone 18 Pro','zh_CN','source'),[])
        raw='productSelectionData: '+json.dumps({'products':[{'partNumber':SKU,'familyType':'iPhone18Pro','dimensionCapacity':'512gb'}]})
        self.assertEqual(parse_catalog(raw,'zh_CN','source')[0]['part'],SKU)
    def test_purchase_browser_modes(self):
        calls=[]
        class Chromium:
            def launch_persistent_context(self, profile, **options):
                calls.append((profile, options));return object()
        class Playwright: chromium=Chromium()
        self.assertIsNotNone(launch_browser(Playwright(), 'profile-a', 'headless'))
        self.assertTrue(calls[-1][1]['headless'])
        self.assertIsNotNone(launch_browser(Playwright(), 'profile-b', 'visible'))
        self.assertFalse(calls[-1][1]['headless'])
        with self.assertRaises(ValueError): normalize_mode('hidden-ish')
    def test_purchase_capabilities_prefer_headless(self):
        state = self.engine.snapshot()
        self.assertEqual(state['purchaseDefault'], 'headless')
        self.assertEqual(state['purchaseModes'], ['headless', 'visible'])
        with patch.dict('os.environ', {'STOCKROOM_CONTAINER':'1'}):
            state = self.engine.snapshot()
        self.assertEqual(state['purchaseModes'], ['headless'])
        self.assertTrue(state['purchaseAvailable'])
    def test_server_auth_and_traversal(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.engine=self.engine;server.token='test-token'
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            root=f'http://127.0.0.1:{server.server_port}'
            with self.assertRaises(urllib.error.HTTPError) as err: urllib.request.urlopen(root+'/api/state')
            self.assertEqual(err.exception.code,403)
            request=urllib.request.Request(root+'/api/state',headers={'X-Session':'test-token'})
            with urllib.request.urlopen(request) as r: self.assertEqual(r.status,200)
            with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(root+'/../config.json')
            bad=urllib.request.Request(root+'/api/control',data=b'{"running":true}',headers={'X-Session':'test-token','Origin':'https://evil.example'})
            with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(bad)
        finally: server.shutdown();server.server_close()

if __name__=='__main__': unittest.main()
