import json
import os
import unittest

from features import gitea_origin
from tests import test_utils


class GiteaOriginTest(unittest.TestCase):
    def test_no_state_file(self):
        self.assertIsNone(gitea_origin.find_origin('a.json', self.state_path))

    def test_runner_not_imported(self):
        self._write_state({'http://g|me|repo': {'runners': ['other.json'], 'scripts': []}})

        self.assertIsNone(gitea_origin.find_origin('a.json', self.state_path))

    def test_full_entry(self):
        params = {'manual_repo': 'me/repo', 'branch': 'dev', 'token_key': 'auto', 'apply': True}
        self._write_state({'http://g|me|repo': {
            'runners': ['a.json'], 'scripts': ['a.py'], 'url': 'http://g', 'owner': 'me', 'repo': 'repo',
            'branch': 'dev', 'commit': 'abc1234', 'commit_time': '2026-11-11T14:02:00+00:00',
            'imported_at': '2026-11-11T14:05:00+00:00', 'update_parameters': params}})

        origin = gitea_origin.find_origin('a.json', self.state_path)

        self.assertEqual('gitea', origin['type'])
        self.assertEqual(('me', 'repo', 'dev', 'abc1234'),
                         (origin['owner'], origin['repo'], origin['branch'], origin['commit']))
        self.assertEqual('Import from Gitea', origin['updater'])
        self.assertEqual(params, origin['updateParameters'])

    def test_old_entry_gets_minimal_update_parameters(self):
        # Written by import_from_gitea.py before 5.1.0: only the file lists
        self._write_state({'http://g|me|repo': {'runners': ['sub/a.json'], 'scripts': []}})

        origin = gitea_origin.find_origin('sub/a.json', self.state_path)

        self.assertEqual(('http://g', 'me', 'repo', 'main'),
                         (origin['url'], origin['owner'], origin['repo'], origin['branch']))
        self.assertEqual({'manual_repo': 'me/repo', 'branch': 'main', 'apply': True}, origin['updateParameters'])
        self.assertIsNone(origin['commit'])

    def test_corrupt_state(self):
        with open(self.state_path, 'w') as f:
            f.write('{nope')

        self.assertIsNone(gitea_origin.find_origin('a.json', self.state_path))

    def _write_state(self, state):
        with open(self.state_path, 'w') as f:
            json.dump(state, f)

    def setUp(self):
        test_utils.setup()
        self.state_path = os.path.join(test_utils.temp_folder, 'gitea_import_state.json')

    def tearDown(self):
        test_utils.cleanup()
