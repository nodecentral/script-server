"""Categories settings tab (scripts/manage_categories.py): every action, against temp files."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))


class ManageCategoriesTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        conf, defaults = os.path.join(self.root, 'conf'), os.path.join(self.root, 'defaults')
        os.makedirs(os.path.join(conf, 'runners'))
        os.makedirs(os.path.join(defaults, 'conf'))
        self.categories = os.path.join(conf, 'categories.json')
        self._write(self.categories, {'_comment': 'keep me', 'default_icon': 'label', 'categories': [
            {'name': 'Finance', 'icon': '£'}, {'name': 'Energy', 'icon': 'label'},
            {'name': 'AI', 'icon': 'label'}, {'name': 'Garden', 'icon': 'label'}]})
        self._write(os.path.join(defaults, 'conf', 'categories.json'), {'categories': [
            {'name': 'Energy', 'icon': 'flash_on'}, {'name': 'AI', 'icon': 'memory'}]})
        with open(os.path.join(defaults, 'material-icons-codepoints'), 'w') as f:
            f.write('flash_on e3e7\nmemory e322\nmovie e02c\nmovie_filter e43a\n')
        self._write(os.path.join(conf, 'runners', 'tariff.json'), {'name': 'Tariff Watch', 'category': 'energy'})
        self._write(os.path.join(self.root, 'state.json'),
                    {'http://g|chris|ss_energy_management': {'runners': ['tariff.json']}})
        os.environ.update(SS_CONF_DIR=conf, DEFAULTS_DIR=defaults, SS_IMPORT_STATE=os.path.join(self.root, 'state.json'),
                          SS_WEB_DIR=os.path.join(self.root, 'web'))
        import manage_categories
        self.m = importlib.reload(manage_categories)

    def tearDown(self):
        shutil.rmtree(self.root)
        for key in ('SS_CONF_DIR', 'DEFAULTS_DIR', 'SS_IMPORT_STATE', 'SS_WEB_DIR'):
            os.environ.pop(key, None)

    @staticmethod
    def _write(path, content):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(content, f)

    def _cats(self):
        with open(self.categories, encoding='utf-8') as f:
            return [(c['name'], c['icon']) for c in json.load(f)['categories']]

    def test_view_changes_nothing(self):
        before = open(self.categories).read()
        self.assertIsNone(self.m.apply('view', '', '', '', ''))
        self.assertEqual(before, open(self.categories).read())

    def test_defaults_fixes_only_generic_icons_the_image_knows(self):
        message = self.m.apply('defaults', '', '', '', '')
        self.assertIn('Energy → flash_on', message)
        self.assertEqual([('Finance', '£'), ('Energy', 'flash_on'), ('AI', 'memory'), ('Garden', 'label')], self._cats())
        self.assertIn('Nothing to change', self.m.apply('defaults', '', '', '', ''))

    def test_icon_checked_against_the_font(self):
        self.m.apply('icon', 'Garden', '', 'flash_on', '')
        self.assertIn(('Garden', 'flash_on'), self._cats())
        with self.assertRaisesRegex(self.m.Refused, 'blank square. Close matches: movie'):
            self.m.apply('icon', 'Garden', '', 'movies', '')
        self.m.apply('icon', 'Garden', '', '🌱', '')
        self.assertIn(('Garden', '🌱'), self._cats())
        with self.assertRaisesRegex(self.m.Refused, 'only one character fits'):
            self.m.apply('icon', 'Garden', '', 'Garden', '')

    def test_add_at_position_and_duplicate_refused(self):
        self.m.apply('add', '', 'Movies', 'movie', '1')
        self.assertEqual(('Movies', 'movie'), self._cats()[0])
        with self.assertRaisesRegex(self.m.Refused, 'already exists'):
            self.m.apply('add', '', 'movies', 'movie', '')

    def test_add_without_icon_uses_the_images(self):
        os.remove(self.categories.replace('categories.json', 'runners/tariff.json'))
        self.m.apply('remove', 'Energy', '', '', '')
        self.m.apply('add', '', 'Energy', '', '')
        self.assertEqual(('Energy', 'flash_on'), self._cats()[-1])

    def test_move(self):
        self.m.apply('move', 'Garden', '', '', '1')
        self.assertEqual('Garden', self._cats()[0][0])
        with self.assertRaisesRegex(self.m.Refused, 'from 1 to 4'):
            self.m.apply('move', 'Garden', '', '', '9')

    def test_remove_refused_while_a_script_uses_it(self):
        with self.assertRaisesRegex(self.m.Refused, '1 script\\(s\\) use Energy \\(Tariff Watch\\)'):
            self.m.apply('remove', 'Energy', '', '', '')
        self.m.apply('remove', 'Garden', '', '', '')
        self.assertNotIn('Garden', [n for n, _ in self._cats()])

    def test_writes_keep_other_keys_layout_and_a_backup(self):
        self.m.apply('icon', 'Garden', '', 'movie', '')
        text = open(self.categories, encoding='utf-8').read()
        self.assertIn('"_comment": "keep me"', text)
        self.assertIn('    {"name": "Garden", "icon": "movie"}\n', text)
        self.assertIn('"icon": "label"', open(self.categories + '.bak', encoding='utf-8').read().split('Garden')[1])

    def test_pick_sentinel_refused(self):
        with self.assertRaisesRegex(self.m.Refused, 'Pick a category'):
            self.m.apply('icon', self.m.PICK, '', 'movie', '')

    def test_table_notes_and_repo(self):
        table = self.m.table_html()
        self.assertIn('generic icon - the image uses <b>flash_on</b>', table)
        self.assertIn('chris/ss_energy_management', table)
        self.assertIn('no scripts use it', table)

    def test_runner_action_values_match_the_script(self):
        with open(os.path.join(REPO, 'conf', 'runners', 'manage_categories.json'), encoding='utf-8') as f:
            runner = json.load(f)
        action = next(p for p in runner['parameters'] if p['env_var'] == 'PARAM_ACTION')
        self.assertEqual(list(self.m.ACTIONS), action['values'])
        self.assertEqual(self.m.ACTIONS, action['values_ui_mapping'])
        category = next(p for p in runner['parameters'] if p['env_var'] == 'PARAM_CATEGORY')
        self.assertEqual(self.m.PICK, category['default'])


if __name__ == '__main__':
    unittest.main()
