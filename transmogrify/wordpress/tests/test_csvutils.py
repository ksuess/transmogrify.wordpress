# -*- coding: utf-8 -*-
import os
import unittest


class CSVUtilsTestCase(unittest.TestCase):

    def test_skip(self):
        from transmogrify.wordpress.blueprints.csvsource import _skip

        row = dict(
            ID='1',
            post_author='',
            post_date='',
            post_date_gmt='',
            post_content='',
            post_title='',
            post_excerpt='',
            post_status='',
            comment_status='',
            ping_status='',
            post_password='',
            post_name='',
            to_ping='',
            pinged='',
            post_modified='',
            post_modified_gmt='',
            post_content_filtered='',
            post_parent='',
            guid='',
            menu_order='',
            post_type='',
            post_mime_type='',
            comment_count='',
        )
        # explicitly skip
        self.assertTrue(_skip(row, ['1']))
        # unknown type; skip
        row['post_type'] = 'foo'
        self.assertTrue(_skip(row, []))
        # revision; skip
        row['post_type'] = 'revision'
        self.assertTrue(_skip(row, []))
        # normal post; process normally
        row['post_type'] = 'post'
        self.assertFalse(_skip(row, []))
        # draft; skip
        row['post_status'] = 'draft'
        self.assertTrue(_skip(row, []))
        # normal post; process normally
        row['post_status'] = 'publish'
        self.assertFalse(_skip(row, []))
        # parse error; skip
        del row['comment_count']
        self.assertTrue(_skip(row, []))

    def test_read_term_relationships(self):
        from transmogrify.wordpress.blueprints.csvutils import read_term_relationships
        path = os.path.dirname(__file__)
        path = os.path.join(path, 'data')
        term_relationships = read_term_relationships(path)
        self.assertEqual(len(term_relationships), 21)
        self.assertIn('10', term_relationships)
        self.assertEqual(term_relationships['10'], ['2', '1'])

    def test_read_term_taxonomy(self):
        from transmogrify.wordpress.blueprints.csvutils import read_term_taxonomy
        path = os.path.dirname(__file__)
        path = os.path.join(path, 'data')
        term_taxonomy = read_term_taxonomy(path)
        self.assertEqual(len(term_taxonomy), 25)
        self.assertIn('1', term_taxonomy)
        self.assertEqual(term_taxonomy['1'].id, '1')
        self.assertEqual(term_taxonomy['1'].taxonomy, 'category')
        self.assertIn('30', term_taxonomy)
        self.assertEqual(term_taxonomy['30'].id, '28')
        self.assertEqual(term_taxonomy['30'].taxonomy, 'post_tag')
