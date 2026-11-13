import unittest
from unittest.mock import patch

import delete_user_flow


class TestDeleteUserFlow(unittest.TestCase):

    @patch('delete_user_flow.requests.post')
    def test_delete_user_uses_uid(self, mock_post):
        mock_post.return_value.json.return_value = {'code': 0, 'message': 'success'}
        result = delete_user_flow.delete_user(
            'https://uc-test.example.com', 123, 'user-token', 'cookie-value',
            'app-token', 'https://crm-test.example.com'
        )
        self.assertEqual(result['code'], 0)
        self.assertEqual(mock_post.call_args.kwargs['json'], {'uid': 123})

    @patch('delete_user_flow.delete_user')
    @patch('delete_user_flow.wait_for_handover')
    @patch('delete_user_flow.create_full_handover')
    @patch('delete_user_flow.api')
    def test_blocked_delete_handover_then_delete(
        self, mock_api, mock_create, mock_wait, mock_delete
    ):
        mock_delete.side_effect = [
            {'code': 200051, 'message': '须交接后才可删除该用户'},
            {'code': 0, 'message': 'success'},
        ]
        mock_api.return_value = {
            'code': 0,
            'data': {
                'form_user': {'uid': 123, 'name': '源用户'},
                'modules': [{'module_class': 'Quotation', 'module_name': '报价单', 'count': 1}],
            },
        }
        mock_create.return_value = {'code': 0, 'data': {'task_no': 'TASK-1'}}
        mock_wait.return_value = {'status': 2, 'status_name': '已完成'}

        result = delete_user_flow.process_user(
            'https://crm.example.com', 'https://uc.example.com',
            'crm-token', 'uc-token', 'cookie', 'app-token', 123, 456,
            'https://crm.example.com',
            poll_interval=0, timeout=1,
        )

        self.assertEqual(result['result'], 'deleted_after_handover')
        self.assertEqual(result['task_no'], 'TASK-1')
        self.assertEqual(mock_delete.call_count, 2)
        mock_create.assert_called_once()


if __name__ == '__main__':
    unittest.main()
