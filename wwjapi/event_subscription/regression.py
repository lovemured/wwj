#!/usr/bin/env python3
"""Staging webhook configuration, edition checks and real callback verification.

Credentials, receiver URLs and tenant-specific data are supplied at runtime.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

STAGING = 'https://lxcrm-api-staging.weiwenjia.com'
SETTINGS = '/api/pc/settings/developer_centers/'


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.lower() in {
            'subscribe_secret', 'authorization', 'token', 'access_token', 'client_secret'
        } else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def success(body):
    if str(body.get('code')) != '0' or body.get('success') is False:
        raise RuntimeError(json.dumps(redact(body), ensure_ascii=False)[:1200])
    return body.get('data')


def receiver_id(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'webhook.site' or parsed.fragment or parsed.query:
        raise ValueError('Use the HTTPS Webhook.site receiver URL, not the #!/view URL')
    identifier = parsed.path.strip('/')
    if str(uuid.UUID(identifier)) != identifier:
        raise ValueError('Receiver path must contain one UUID')
    return identifier


def callback_matches(payload, event, organization_id, ids):
    if payload.get('event_type') != event or payload.get('organization_id') != organization_id:
        return False
    found = set()
    entity_id = (payload.get('entity') or {}).get('id')
    if entity_id is not None:
        found.add(str(entity_id))
    data = payload.get('data') or {}
    for key in ('ids', 'created_ids', 'updated_ids'):
        found.update(str(i) for i in data.get(key, []))
    return bool(found & {str(i) for i in ids})


class Client:
    def __init__(self, args):
        self.base = args.api.rstrip('/')
        self.callback = args.callback
        self.receiver = receiver_id(self.callback) if self.callback else None
        self.out = Path(args.output)
        self.out.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        token = os.environ['CRM_WEBHOOK_TOKEN']
        self.session.headers['Authorization'] = f'Token token="{token}",device="web"'

    def save(self, name, value):
        (self.out / (name + '.json')).write_text(
            json.dumps(redact(value), ensure_ascii=False, indent=2), encoding='utf-8')

    def api(self, method, path, body=None, mobile=False):
        if not path.startswith('/api/') or '://' in path:
            raise ValueError('Business paths must start with /api/')
        headers = {}
        if mobile:
            headers = {'Authorization': self.session.headers['Authorization'].replace(
                'device="web"', 'device="lxcrm_duli",version_code="4.0.1"'),
                'Origin': 'https://crmh5-staging.weiwenjia.com',
                'X-Requested-With': 'com.lixiaoyun.aike'}
        response = self.session.request(method, self.base + path, json=body, headers=headers, timeout=45)
        try:
            result = response.json()
        except ValueError:
            result = {'message': response.text[:500]}
        item = {'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'method': method,
                'path': path, 'request': body, 'http_status': response.status_code,
                'response': result}
        with (self.out / 'requests.ndjson').open('a', encoding='utf-8') as output:
            output.write(json.dumps(redact(item), ensure_ascii=False) + '\n')
        return result

    def receipts(self):
        # Do not forward the CRM Authorization header to Webhook.site.
        all_requests = []
        page = 1
        while True:
            response = requests.get(f'https://webhook.site/token/{self.receiver}/requests',
                                    params={'sorting': 'newest', 'per_page': 100, 'page': page}, timeout=30)
            response.raise_for_status()
            body = response.json()
            all_requests.extend(body['data'])
            if len(all_requests) >= body['total'] or not body['data']:
                break
            page += 1
        self.save('receipts', all_requests)
        return all_requests

    def configure(self, events):
        catalog = self.api('GET', SETTINGS + 'event_types')
        success(catalog)
        before = self.api('GET', SETTINGS + 'show_webhook')
        success(before)
        self.save('subscription-before-' + uuid.uuid4().hex[:8], before)
        maximum = 20 if catalog.get('edition') == 'basic' else 40
        if len(events) > maximum or len(events) != len(set(events)):
            raise ValueError(f'Expected unique events, at most {maximum} for {catalog.get("edition")}')
        success(self.api('POST', SETTINGS + 'save_webhook',
                         {'webhook': {'callback_url': self.callback, 'subscribed_events': events}}))
        after = self.api('GET', SETTINGS + 'show_webhook')
        data = success(after)
        assert data['callback_url'] == self.callback and set(data['subscribed_events']) == set(events)
        self.save('subscription', after)

    def wait_for(self, event, organization_id, ids, baseline, wait):
        deadline = time.monotonic() + wait
        while True:
            matches = []
            for receipt in self.receipts():
                if receipt['uuid'] in baseline:
                    continue
                try:
                    payload = json.loads(receipt.get('content') or '')
                except ValueError:
                    continue
                if isinstance(payload, dict) and callback_matches(payload, event, organization_id, ids):
                    matches.append({'uuid': receipt['uuid'], 'payload': payload})
            if matches or time.monotonic() >= deadline:
                return matches
            time.sleep(min(5, max(0, deadline - time.monotonic())))


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def event_names(path):
    names = load_json(path)
    if not isinstance(names, list) or not names or not all(isinstance(x, str) and x for x in names):
        raise ValueError('Events file must be a nonempty JSON array of names')
    if len(names) != len(set(names)):
        raise ValueError('Events file contains duplicate names')
    return names


def denied_checks(client, events):
    before = success(client.api('GET', SETTINGS + 'show_webhook'))
    if not before:
        raise ValueError('Save a valid basic subscription first')
    baseline = before['subscribed_events'][:1]
    assert baseline, 'Need one existing basic event for a mixed-subscription check'
    results = []
    for event in events:
        result = client.api('POST', SETTINGS + 'save_webhook', {'webhook': {
            'callback_url': before['callback_url'], 'subscribed_events': baseline + [event]}})
        rejected = (result.get('success') is False and str(result.get('code')) != '0'
                    and '无效或当前版本不支持的事件类型' in result.get('message', '')
                    and event in result.get('message', ''))
        after = success(client.api('GET', SETTINGS + 'show_webhook'))
        unchanged = (after['subscribed_events'] == before['subscribed_events']
                     and after['callback_url'] == before['callback_url'])
        results.append({'event': event, 'rejected': rejected, 'configuration_unchanged': unchanged,
                        'response': result})
        client.save('edition-checks', results)
        if not unchanged:
            success(client.api('POST', SETTINGS + 'save_webhook', {'webhook': {
                'callback_url': before['callback_url'], 'subscribed_events': before['subscribed_events']}}))
            restored = success(client.api('GET', SETTINGS + 'show_webhook'))
            assert restored['subscribed_events'] == before['subscribed_events']
            assert restored['callback_url'] == before['callback_url']
    return results


def mobile_checkin(client, wait):
    identity = success(client.api('GET', '/api/v2/user/info'))
    config = success(client.api('GET', SETTINGS + 'show_webhook'))
    assert config and config['callback_url'] == client.callback
    assert {'checkin.cold_visit_create', 'checkin.delete'} <= set(config['subscribed_events'])
    baseline = {r['uuid'] for r in client.receipts()}
    ticket = str(uuid.uuid4())
    address = {'lat': 31.217022, 'lng': 121.532576, 'offDistance': 10,
               'detail_address': '自动化合成测试地址'}
    body = {'address_self': address, 'address_checkable': address, 'update_entity_address': False,
            'message': 'WH-' + ticket, 'checkPattern': {'status': '陌拜'}, 'isApaas': False, 'uuid': ticket}
    data = success(client.api('POST', '/api/v3/checkin?request_ticket=' + ticket, body, mobile=True))
    entity_id = data['id']
    client.save('created-checkin', {'id': entity_id, 'deleted': False})
    created = []
    try:
        info = success(client.api('GET', f'/api/v3/checkin/{entity_id}', mobile=True))['checkin_info']
        assert info['organization_id'] == identity['organization_id'] and info['checkin_type'] == 0
        created = client.wait_for('checkin.cold_visit_create', identity['organization_id'], [entity_id], baseline, wait)
    finally:
        success(client.api('DELETE', f'/api/v3/checkin/{entity_id}', mobile=True))
        readback = client.api('GET', f'/api/v3/checkin/{entity_id}', mobile=True)
        assert readback.get('code') == 2009, readback
        client.save('created-checkin', {'id': entity_id, 'deleted': True})
    deleted = client.wait_for('checkin.delete', identity['organization_id'], [entity_id], baseline, wait)
    result = {'id': entity_id, 'create_matches': created, 'delete_matches': deleted}
    client.save('mobile-checkin-result', result)
    return bool(created and deleted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default=STAGING)
    parser.add_argument('--callback', default=os.environ.get('CRM_WEBHOOK_CALLBACK'))
    parser.add_argument('--output', default='event_subscription/results/' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('catalog')
    configure = commands.add_parser('configure')
    configure.add_argument('--events', required=True, help='JSON array of exact event names')
    denied = commands.add_parser('check-denied')
    denied.add_argument('--events', required=True, help='JSON array of expected enterprise-only names')
    verify = commands.add_parser('verify')
    verify.add_argument('--event', required=True)
    verify.add_argument('--organization-id', type=int, required=True)
    verify.add_argument('--ids', type=int, nargs='+', required=True)
    verify.add_argument('--wait', type=int, default=30)
    verify.add_argument('--baseline', help='Earlier receipts.json; excludes pre-existing callbacks')
    commands.add_parser('snapshot')
    checkin = commands.add_parser('mobile-checkin')
    checkin.add_argument('--wait', type=int, default=30)
    args = parser.parse_args()
    if args.api.rstrip('/') != STAGING:
        parser.error('This regression tool only supports the staging API')
    if not os.environ.get('CRM_WEBHOOK_TOKEN'):
        parser.error('Set CRM_WEBHOOK_TOKEN in the environment')
    if args.command in {'configure','verify','snapshot','mobile-checkin'} and not args.callback:
        parser.error('Provide --callback or CRM_WEBHOOK_CALLBACK')
    if hasattr(args, 'wait') and not 0 <= args.wait <= 300:
        parser.error('--wait must be between 0 and 300 seconds')
    client = Client(args)
    if args.command == 'catalog':
        result = client.api('GET', SETTINGS + 'event_types')
        success(result)
        client.save('catalog', result)
        print(json.dumps(redact(result), ensure_ascii=False))
    elif args.command == 'configure':
        client.configure(event_names(args.events))
        print('Subscription saved and read back')
    elif args.command == 'check-denied':
        results = denied_checks(client, event_names(args.events))
        print(f'Rejected {sum(r["rejected"] and r["configuration_unchanged"] for r in results)}/{len(results)}')
        return 0 if all(r['rejected'] and r['configuration_unchanged'] for r in results) else 1
    elif args.command == 'snapshot':
        print(f'Archived {len(client.receipts())} requests')
    elif args.command == 'verify':
        baseline = {r['uuid'] for r in load_json(args.baseline)} if args.baseline else set()
        result = client.wait_for(args.event, args.organization_id, args.ids, baseline, args.wait)
        client.save('matched-callbacks', result)
        print(f'Matched {len(result)} callbacks')
        return 0 if result else 1
    elif args.command == 'mobile-checkin':
        passed = mobile_checkin(client, args.wait)
        print('PASS' if passed else 'Callback missing; inspect receiver health and evidence')
        return 0 if passed else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
