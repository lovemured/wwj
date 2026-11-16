"""Offline checks: callback identity, failed API responses and negative-save recovery."""
import unittest
from unittest.mock import Mock

from regression import callback_matches, denied_checks, receiver_id, redact, success


class RegressionTests(unittest.TestCase):
    def test_exact_event_enterprise_and_entity_are_required(self):
        payload = {'event_type':'lead.create','organization_id':42,'entity':{'id':7},'data':{}}
        self.assertTrue(callback_matches(payload,'lead.create',42,[7]))
        self.assertFalse(callback_matches(payload,'lead.create',43,[7]))
        self.assertFalse(callback_matches(payload,'lead.create',42,[8]))
        self.assertFalse(callback_matches(payload,'customer.create',42,[7]))
        payload['event_type'] = 'test.ping'
        self.assertFalse(callback_matches(payload,'lead.create',42,[7]))

    def test_batches_and_imports_match_ids(self):
        for key in ('ids','created_ids','updated_ids'):
            payload = {'event_type':'customer.import','organization_id':42,
                       'entity':{'id':None},'data':{key:[7,8]}}
            self.assertTrue(callback_matches(payload,'customer.import',42,[8]))
            self.assertFalse(callback_matches(payload,'customer.import',42,[9]))

    def test_missing_success_code_cannot_pass(self):
        for body in ({'message':'对象不存在'}, {'code':-1}, {'code':0,'success':False}):
            with self.assertRaises(RuntimeError):
                success(body)
        self.assertEqual(success({'code':'0','data':{'id':7}}),{'id':7})

    def test_nested_credentials_are_redacted(self):
        value = {'data':{'subscribe_secret':'secret'},'items':[{'Authorization':'token'}]}
        self.assertEqual(redact(value), {'data':{'subscribe_secret':'[REDACTED]'},
                                       'items':[{'Authorization':'[REDACTED]'}]})
        self.assertEqual(value['data']['subscribe_secret'],'secret')

    def test_viewer_url_is_rejected(self):
        token = '00000000-0000-4000-8000-000000000001'
        self.assertEqual(receiver_id('https://webhook.site/'+token),token)
        for url in ('https://webhook.site/#!/view/'+token,
                    'https://example.com/'+token, 'https://webhook.site/'+token+'/requests'):
            with self.assertRaises(ValueError):
                receiver_id(url)

    def test_unexpected_save_is_restored_and_still_fails(self):
        original = {'callback_url':'https://example.test/receiver','subscribed_events':['lead.create']}
        changed = dict(original, subscribed_events=['lead.create','customer.batch_update'])
        client = Mock()
        client.api.side_effect = [
            {'code':0,'data':original}, {'code':0,'success':True},
            {'code':0,'data':changed}, {'code':0,'data':original}, {'code':0,'data':original}]
        results = denied_checks(client,['customer.batch_update'])
        self.assertFalse(results[0]['rejected'])
        self.assertFalse(results[0]['configuration_unchanged'])
        restoration = client.api.call_args_list[3].args[2]
        self.assertEqual(restoration['webhook'],original)

    def test_other_errors_are_not_edition_rejection(self):
        original = {'callback_url':'https://example.test/receiver','subscribed_events':['lead.create']}
        client = Mock()
        client.api.side_effect = [{'code':0,'data':original},
                                  {'code':-1,'success':False,'message':'最多只能订阅20个事件类型'},
                                  {'code':0,'data':original}]
        result = denied_checks(client,['customer.batch_update'])
        self.assertFalse(result[0]['rejected'])


if __name__ == '__main__':
    unittest.main()
