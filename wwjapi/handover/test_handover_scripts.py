#!/usr/bin/env python3
"""交接脚本单元测试 - mock API 请求，验证逻辑正确性"""
import unittest
from unittest.mock import patch, MagicMock
import sys, os, io, json

sys.path.insert(0, os.path.dirname(__file__))
from handover_common import api, infer_pc_api, STATUS_MAP
import create_handover
import handover_tasks
import resume_handover


class TestHandoverCommon(unittest.TestCase):

    def test_infer_pc_api_staging(self):
        self.assertEqual(
            infer_pc_api('https://lxcrm-staging.weiwenjia.com'),
            'https://lxcrm-api-staging.weiwenjia.com'
        )

    def test_infer_pc_api_test(self):
        self.assertEqual(
            infer_pc_api('https://lxcrm-test.weiwenjia.com'),
            'https://lxcrm-api-test.weiwenjia.com'
        )

    def test_infer_pc_api_no_change(self):
        self.assertEqual(
            infer_pc_api('https://custom.example.com'),
            'https://custom.example.com'
        )

    def test_infer_pc_api_strips_trailing_slash(self):
        self.assertEqual(
            infer_pc_api('https://lxcrm-staging.weiwenjia.com/'),
            'https://lxcrm-api-staging.weiwenjia.com'
        )

    @patch('handover_common.requests.get')
    def test_api_get_success(self, mock_get):
        mock_get.return_value.json.return_value = {'code': 0, 'data': {'key': 'val'}}
        result = api('https://api.example.com', 'token123', 'grove_tasks')
        self.assertEqual(result['code'], 0)
        self.assertEqual(result['data']['key'], 'val')
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('/api/pc/grove_tasks', args[0])
        self.assertEqual(kwargs['headers']['Authorization'], 'Token token=token123')

    @patch('handover_common.requests.request')
    def test_api_post_success(self, mock_request):
        mock_request.return_value.json.return_value = {'code': 0, 'data': {}}
        result = api('https://api.example.com', 'token123', 'grove_tasks',
                     {'key': 'val'}, method='POST')
        self.assertEqual(result['code'], 0)
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(kwargs['json'], {'key': 'val'})
        self.assertEqual(args[0], 'POST')

    @patch('handover_common.requests.get')
    def test_api_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError('Connection refused')
        result = api('https://api.example.com', 'token123', 'grove_tasks')
        self.assertEqual(result['code'], -1)
        self.assertIn('请求失败', result['message'])

    def test_status_map_completeness(self):
        for s in range(7):
            self.assertIn(s, STATUS_MAP)
        self.assertEqual(STATUS_MAP[0], '待执行')
        self.assertEqual(STATUS_MAP[2], '已完成')
        self.assertEqual(STATUS_MAP[3], '执行失败')


class TestCreateHandover(unittest.TestCase):

    def setUp(self):
        self.pc_api = 'https://lxcrm-api-staging.weiwenjia.com'
        self.token = 'test-token'

    @patch('create_handover.api')
    def test_check_assets_success(self, mock_api):
        mock_api.return_value = {
            'code': 0,
            'data': {
                'modules': [
                    {'module_name': '线索', 'module_class': 'lead', 'count': 10},
                    {'module_name': '客户', 'module_class': 'customer', 'count': 5},
                ]
            }
        }
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.check_assets(self.pc_api, self.token, 123)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIsNotNone(result)
        self.assertIn('线索', output)
        self.assertIn('10 条', output)
        self.assertIn('5 条', output)
        self.assertIn('合计: 15 条', output)

    @patch('create_handover.api')
    def test_check_assets_empty(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {'modules': []}}
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.check_assets(self.pc_api, self.token, 123)
        sys.stdout = sys.__stdout__
        self.assertIsNotNone(result)
        self.assertIn('没有可交接的数据', captured.getvalue())

    @patch('create_handover.api')
    def test_check_assets_failure(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '用户不存在'}
        result = create_handover.check_assets(self.pc_api, self.token, 999)
        self.assertIsNone(result)

    @patch('create_handover.api')
    def test_check_capacity_success(self, mock_api):
        mock_api.return_value = {
            'code': 0,
            'data': {
                'modules': [{
                    'module_name': '线索',
                    'module_class': 'lead',
                    'data': {
                        'enable_limit': True,
                        'limit_type': 'count',
                        'limits': [{'source_name': '线索', 'current_count': 3, 'limit_count': 10}],
                        'pass': True,
                    }
                }]
            }
        }
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.check_capacity(self.pc_api, self.token, 1, 2, ['lead'])
        sys.stdout = sys.__stdout__
        self.assertIsNotNone(result)
        output = captured.getvalue()
        self.assertIn('✅ 是', output)
        self.assertIn('3/10', output)

    @patch('create_handover.api')
    def test_check_capacity_failure(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '容量不足'}
        result = create_handover.check_capacity(self.pc_api, self.token, 1, 2, ['lead'])
        self.assertIsNone(result)

    @patch('create_handover.api')
    def test_create_handover_success(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {'task_no': 'H20250624001'}}
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.create_handover(
            self.pc_api, self.token, 1, 2, 2, ['lead', 'customer'],
            from_user_name='测试用户')
        sys.stdout = sys.__stdout__
        self.assertIsNotNone(result)
        output = captured.getvalue()
        self.assertIn('创建成功', output)
        self.assertIn('H20250624001', output)
        # Verify payload structure
        call_args = mock_api.call_args
        self.assertEqual(call_args[0][2], 'grove_tasks')
        payload = call_args[0][3]
        self.assertEqual(payload['job_type'], 'Handover')
        self.assertEqual(payload['job_args']['from_user_uid'], 1)
        self.assertEqual(payload['job_args']['from_user']['name'], '测试用户')
        self.assertEqual(len(payload['job_args']['entity_data']), 2)

    @patch('create_handover.api')
    def test_create_handover_failure(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '模块不存在'}
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.create_handover(
            self.pc_api, self.token, 1, 2, 2, ['invalid_module'])
        sys.stdout = sys.__stdout__
        self.assertIn('创建失败', captured.getvalue())

    @patch('create_handover.api')
    def test_create_handover_with_module_names(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {'task_no': 'H20250624002'}}
        captured = io.StringIO()
        sys.stdout = captured
        result = create_handover.create_handover(
            self.pc_api, self.token, 1, 2, 2,
            ['lead', 'data_93171715128380'],
            module_names=['线索', '项目跟进'],
            from_user_name='测试用户')
        sys.stdout = sys.__stdout__
        self.assertIsNotNone(result)
        self.assertIn('创建成功', captured.getvalue())


class TestHandoverTasks(unittest.TestCase):

    def setUp(self):
        self.pc_api = 'https://lxcrm-api-staging.weiwenjia.com'
        self.token = 'test-token'

    @patch('handover_tasks.api')
    def test_list_tasks_success(self, mock_api):
        mock_api.return_value = {
            'code': 0,
            'data': {
                'list': [
                    {
                        'task_no': 'H001', 'status': 2, 'status_name': '已完成',
                        'created_at': '2025-01-01 10:00',
                        'ended_at': '2025-01-01 10:05',
                        'operator': {'uid': 1, 'name': '管理员'},
                        'job_args': {
                            'from_user_uid': 1,
                            'entity_data': [
                                {'module_name': '线索', 'module_class': 'lead'},
                                {'module_name': '客户', 'module_class': 'customer'},
                            ],
                        },
                    },
                    {
                        'task_no': 'H002', 'status': 3, 'status_name': '执行失败',
                        'created_at': '2025-01-02 14:00',
                        'operator': {'uid': 4, 'name': '赵六'},
                        'job_args': {
                            'from_user_uid': 4,
                            'entity_data': [
                                {'module_name': '线索', 'module_class': 'lead'},
                            ],
                        },
                    },
                ]
            }
        }
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.list_tasks(self.pc_api, self.token, 1)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('H001', output)
        self.assertIn('已完成', output)
        self.assertIn('H002', output)
        self.assertIn('执行失败', output)
        self.assertIn('共 2 条记录', output)

    @patch('handover_tasks.api')
    def test_list_tasks_empty(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {'total_count': 0, 'list': []}}
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.list_tasks(self.pc_api, self.token, 1)
        sys.stdout = sys.__stdout__
        self.assertIn('暂无交接任务', captured.getvalue())

    @patch('handover_tasks.api')
    def test_list_tasks_failure(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '无权限'}
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.list_tasks(self.pc_api, self.token, 1)
        sys.stdout = sys.__stdout__
        self.assertIn('查询失败', captured.getvalue())

    @patch('handover_tasks.api')
    def test_task_detail_success(self, mock_api):
        mock_api.return_value = {
            'code': 0,
            'data': {
                'task_no': 'H001', 'status': 4, 'status_name': '部分成功',
                'created_at': '2025-01-01 10:00',
                'started_at': '2025-01-01 10:05',
                'ended_at': '2025-01-01 10:10',
                'operator': {'uid': 99, 'name': '管理员'},
                'job_args': {
                    'from_user_uid': 1,
                    'entity_data': [
                        {'module_class': 'lead', 'module_name': '线索', 'to_user_uid': 2, 'to_assist_user_uid': 3},
                        {'module_class': 'customer', 'module_name': '客户', 'to_user_uid': 2, 'to_assist_user_uid': 3},
                    ],
                },
                'job_results': {
                    'total_module_count': 2,
                    'completed_module_count': 1,
                    'failed_module_count': 0,
                    'from_user': {'uid': 1, 'name': '张三'},
                    'entity_data': [
                        {
                            'module_name': '线索', 'module_class': 'lead',
                            'status_name': '已完成', 'progress': 100.0,
                            'total_count': 10, 'final_count': 8,
                            'to_user': {'name': '李四'}, 'to_assist_user': {'name': '王五'},
                            'errors': ['2条数据归属人已变更'],
                        },
                        {
                            'module_name': '客户', 'module_class': 'customer',
                            'status_name': '已完成', 'progress': 100.0,
                            'total_count': 5, 'final_count': 5,
                            'to_user': {'name': '李四'}, 'to_assist_user': {'name': '王五'},
                            'errors': [],
                        },
                    ],
                },
            }
        }
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.task_detail(self.pc_api, self.token, 'H001')
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('H001', output)
        self.assertIn('部分成功', output)
        self.assertIn('线索', output)
        self.assertIn('8/10', output)
        self.assertIn('2条数据', output)
        self.assertIn('客户', output)
        self.assertIn('5 条', output)
        self.assertIn('归属人已变更', output)

    @patch('handover_tasks.api')
    def test_task_detail_failure(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '任务不存在'}
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.task_detail(self.pc_api, self.token, 'INVALID')
        sys.stdout = sys.__stdout__
        self.assertIn('查询失败', captured.getvalue())


class TestResumeHandover(unittest.TestCase):

    def setUp(self):
        self.pc_api = 'https://lxcrm-api-staging.weiwenjia.com'
        self.token = 'test-token'

    @patch('resume_handover.api')
    def test_resume_failed_task(self, mock_api):
        def side_effect(pc_api, token, path, data=None, method='GET'):
            if 'grove_tasks/' in path and '/resume' not in path:
                return {'code': 0, 'data': {
                    'task_no': 'H001', 'status': 3, 'status_name': '执行失败',
                    'operator': {'name': '管理员', 'uid': 99},
                    'job_args': {'from_user_uid': 1},
                }}
            return {'code': 0, 'data': {}}
        mock_api.side_effect = side_effect
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(self.pc_api, self.token, 'H001')
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('执行失败', output)
        self.assertIn('已重新开始', output)

    @patch('resume_handover.api')
    def test_resume_completed_task(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {
            'task_no': 'H001', 'status': 2, 'status_name': '已完成',
            'operator': {'name': '管理员', 'uid': 99},
            'job_args': {'from_user_uid': 1},
        }}
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(self.pc_api, self.token, 'H001')
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('已完成', output)
        self.assertIn('无需恢复', output)

    @patch('resume_handover.api')
    def test_resume_running_task(self, mock_api):
        mock_api.return_value = {'code': 0, 'data': {
            'task_no': 'H001', 'status': 1, 'status_name': '执行中',
            'operator': {'name': '管理员', 'uid': 99},
            'job_args': {'from_user_uid': 1},
        }}
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(self.pc_api, self.token, 'H001')
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('执行中', output)
        self.assertIn('请稍后再试', output)

    @patch('resume_handover.api')
    def test_resume_not_found(self, mock_api):
        mock_api.return_value = {'code': -1, 'message': '任务不存在'}
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(self.pc_api, self.token, 'INVALID')
        sys.stdout = sys.__stdout__
        self.assertIn('查询任务失败', captured.getvalue())

    @patch('resume_handover.api')
    def test_resume_api_failure(self, mock_api):
        def side_effect(pc_api, token, path, data=None, method='GET'):
            if 'grove_tasks/' in path and '/resume' not in path:
                return {'code': 0, 'data': {
                    'task_no': 'H001', 'status': 3, 'status_name': '执行失败',
                    'operator': {'name': '管理员', 'uid': 99},
                    'job_args': {'from_user_uid': 1},
                }}
            return {'code': -1, 'message': '服务异常'}
        mock_api.side_effect = side_effect
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(self.pc_api, self.token, 'H001')
        sys.stdout = sys.__stdout__
        self.assertIn('恢复失败', captured.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
