import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from cloudbase_http import CloudBaseError, request_bridge
from cloudbase_server import build_server, StartupError


class StartupDiagnosticsTests(unittest.TestCase):
    def test_missing_variables_and_origin_format_are_named_without_values(self):
        env = {'PUBLIC_ORIGIN': 'https://family.example/', 'FAMILY_USERNAME': 'family',
               'FAMILY_PASSWORD': 'do-not-print-this-password', 'CLOUDBASE_ENV_ID': 'test-env',
               'CLOUDBASE_API_KEY': 'do-not-print-this-key'}
        for name in env:
            missing = dict(env)
            missing.pop(name)
            with patch.dict(os.environ, missing, clear=True), self.assertRaises(StartupError) as error:
                build_server()
            self.assertIn(name, str(error.exception))
            self.assertNotIn('do-not-print', str(error.exception))
        with patch.dict(os.environ, env, clear=True), self.assertRaises(StartupError) as error:
            build_server()
        self.assertIn('PUBLIC_ORIGIN', str(error.exception))

    def test_gateway_diagnostics_only_include_allowlisted_error_codes(self):
        env = {'CLOUDBASE_ENV_ID': 'test-env', 'CLOUDBASE_API_KEY': 'secret-value'}
        for status, code in [(401, 'UNAUTHORIZED'), (403, 'ACTION_FORBIDDEN'), (400, 'DATABASE_42883'), (500, 'secret-value')]:
            response = io.BytesIO(json.dumps({'code': code, 'message': 'secret-value child-data'}).encode())
            failure = HTTPError('https://gateway', status, 'secret-value', {}, response)
            with patch.dict(os.environ, env, clear=True), patch('urllib.request.build_opener', side_effect=failure), self.assertRaises(CloudBaseError) as error:
                request_bridge({})
            self.assertIn(f'HTTP {status}', str(error.exception))
            if code != 'secret-value':
                self.assertIn(code, str(error.exception))
            self.assertNotIn('secret-value', str(error.exception))
            self.assertNotIn('child-data', str(error.exception))
