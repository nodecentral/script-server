"""A runner that fails to load says why (which parameter, what failed)."""
import os
import unittest

from auth.authorization import Authorizer, ANY_USER, EmptyGroupProvider
from auth.user import User
from config.config_service import ConfigService, CorruptConfigFileException
from model.script_config import ParameterLoadException
from tests import test_utils
from tests.test_utils import create_script_param_config
from utils import file_utils
from utils.process_utils import ExecutionException
from web.script_config_socket import describe_load_error, _truncate_utf8


class ParameterLoadExceptionTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        test_utils.setup()

    def tearDown(self):
        super().tearDown()
        test_utils.cleanup()

    def _model_with_values_script(self, script):
        param = create_script_param_config('repo', type='list', values_script=script)
        return test_utils.create_config_model('conf_x', parameters=[param])

    def test_failing_values_script_names_the_parameter(self):
        with self.assertRaises(ParameterLoadException) as ctx:
            self._model_with_values_script("echo 'no gitea' >&2; exit 3")

        error = ctx.exception
        self.assertEqual('repo', error.parameter_name)
        self.assertIsInstance(error.cause, ExecutionException)
        self.assertIn('Parameter "repo"', str(error))
        self.assertIn('Code 3', str(error))
        self.assertIn('no gitea', str(error))

    def test_values_script_without_execute_bit(self):
        script = test_utils.create_file('noexec.sh', text='#!/bin/sh\necho a\n')
        os.chmod(script, 0o644)

        with self.assertRaises(ParameterLoadException) as ctx:
            self._model_with_values_script(script)

        self.assertIn('Code 126', str(ctx.exception))

    def test_working_values_script_still_loads(self):
        model = self._model_with_values_script('echo a; echo b')
        self.assertEqual(['a', 'b'], model.find_parameter('repo').values)


class DescribeLoadErrorTest(unittest.TestCase):
    def test_parameter_error_is_one_line(self):
        cause = ExecutionException(126, '/bin/sh: x.sh: Permission denied', '')
        error = ParameterLoadException('repo', cause)
        error.__cause__ = cause

        self.assertEqual('Parameter "repo": Execution failed. Code 126: /bin/sh: x.sh: Permission denied',
                         describe_load_error(error))

    def test_unrelated_cause_is_appended(self):
        try:
            try:
                raise KeyError('missing')
            except KeyError as e:
                raise ValueError('bad runner') from e
        except ValueError as e:
            detail = describe_load_error(e)

        self.assertEqual("bad runner\nCaused by: 'missing'", detail)

    def test_long_detail_is_cut(self):
        self.assertEqual(23, len(describe_load_error(Exception('x' * 100), max_length=20)))

    def test_truncate_utf8_keeps_whole_characters(self):
        self.assertEqual('££', _truncate_utf8('£££', 5))
        self.assertEqual('short', _truncate_utf8('short', 120))


class CorruptConfigDetailTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        test_utils.setup()
        self.user = User('user1', {})
        self.admin = User('admin_user', {})
        authorizer = Authorizer(ANY_USER, ['admin_user'], [], [], EmptyGroupProvider())
        self.config_service = ConfigService(authorizer, test_utils.temp_folder, True, test_utils.process_invoker)

        path = os.path.join(test_utils.temp_folder, 'runners', 'broken.json')
        file_utils.write_file(path, '{"name": "broken",\n "parameters": [\n')

    def tearDown(self):
        super().tearDown()
        test_utils.cleanup()

    def test_admin_sees_file_and_json_error(self):
        with self.assertRaises(CorruptConfigFileException) as ctx:
            self.config_service.load_config_model('broken', self.admin)

        message = str(ctx.exception)
        self.assertTrue(message.startswith('Cannot parse script config file: broken.json: '), message)
        self.assertIn('line 4 column 1', message)

    def test_other_users_get_the_plain_message(self):
        with self.assertRaises(CorruptConfigFileException) as ctx:
            self.config_service.load_config_model('broken', self.user)

        self.assertEqual('Cannot parse script config file', str(ctx.exception))
