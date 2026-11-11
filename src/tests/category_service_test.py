import json
import os
import unittest

from config.category_service import CategoryService, to_external
from tests import test_utils


class CategoryServiceTest(unittest.TestCase):
    def test_no_file_creates_one_with_used_categories(self):
        resolved = self.service.resolve(['Finance', None, 'Music'])

        self.assertEqual([{'name': 'Finance', 'icon': 'label'}, {'name': 'Music', 'icon': 'label'}],
                         resolved['categories'])
        self.assertEqual({'name': 'Uncategorised', 'icon': 'label_outline'}, resolved['uncategorised'])
        self.assertEqual(['Finance', 'Music'], [c['name'] for c in self._read_file()['categories']])

    def test_known_categories_keep_their_icon_and_order(self):
        self._write_file({'default_icon': 'bookmark',
                          'categories': [{'name': 'Music', 'icon': 'music_note'},
                                         {'name': 'Finance', 'icon': '£'}]})

        resolved = self.service.resolve(['Finance', 'Music'])

        self.assertEqual([{'name': 'Music', 'icon': 'music_note'}, {'name': 'Finance', 'icon': '£'}],
                         resolved['categories'])

    def test_new_category_appended_with_default_icon_and_existing_untouched(self):
        self._write_file({'_comment': 'keep me',
                          'default_icon': 'bookmark',
                          'categories': [{'name': 'Finance', 'icon': '£'}]})

        self.service.resolve(['Finance', 'Garden'])

        content = self._read_file()
        self.assertEqual('keep me', content['_comment'])
        self.assertEqual([{'name': 'Finance', 'icon': '£'}, {'name': 'Garden', 'icon': 'bookmark'}],
                         content['categories'])

    def test_case_insensitive_match_uses_file_spelling(self):
        self._write_file({'categories': [{'name': 'Finance', 'icon': '£'}]})

        resolved = self.service.resolve(['finance', ' FINANCE '])

        self.assertEqual(1, len(resolved['categories']))
        self.assertEqual('Finance', CategoryService.canonical_name('finance', resolved))
        self.assertEqual('Finance', CategoryService.canonical_name(' FINANCE ', resolved))
        self.assertIsNone(CategoryService.canonical_name('', resolved))
        self.assertEqual(1, len(self._read_file()['categories']))

    def test_uncategorised_name_is_not_added_as_category(self):
        resolved = self.service.resolve(['uncategorised'])

        self.assertEqual([], resolved['categories'])
        self.assertIsNone(CategoryService.canonical_name('uncategorised', resolved))

    def test_custom_uncategorised(self):
        self._write_file({'uncategorised': {'name': 'Other', 'icon': 'more_horiz'}})

        resolved = self.service.resolve([])

        self.assertEqual({'name': 'Other', 'icon': 'more_horiz'}, to_external(resolved)['uncategorised'])

    def test_corrupt_file_is_not_overwritten(self):
        path = os.path.join(test_utils.temp_folder, 'categories.json')
        with open(path, 'w') as f:
            f.write('{broken')

        resolved = self.service.resolve(['Finance'])

        self.assertEqual(['Finance'], [c['name'] for c in resolved['categories']])
        with open(path) as f:
            self.assertEqual('{broken', f.read())

    def test_shipped_categories_file_is_valid(self):
        shipped = os.path.join(os.path.dirname(__file__), '..', '..', 'conf', 'categories.json')
        with open(shipped, encoding='utf-8') as f:
            content = json.load(f)

        names = [c['name'] for c in content['categories']]
        self.assertEqual(len(names), len(set(n.lower() for n in names)))
        for entry in content['categories']:
            self.assertTrue(entry['icon'])

    def _write_file(self, content):
        with open(os.path.join(test_utils.temp_folder, 'categories.json'), 'w', encoding='utf-8') as f:
            json.dump(content, f)

    def _read_file(self):
        with open(os.path.join(test_utils.temp_folder, 'categories.json'), encoding='utf-8') as f:
            return json.load(f)

    def setUp(self):
        super().setUp()
        test_utils.setup()
        self.service = CategoryService(test_utils.temp_folder)

    def tearDown(self):
        super().tearDown()
        test_utils.cleanup()
