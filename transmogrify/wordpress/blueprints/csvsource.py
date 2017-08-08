# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from DateTime import DateTime
from OFS.ObjectManager import bad_id
from transmogrify.wordpress.blueprints.csvutils import get_display_names
from transmogrify.wordpress.blueprints.csvutils import get_taxonomies
from transmogrify.wordpress.logger import logger
from transmogrify.wordpress.utils import fix_id
from transmogrify.wordpress.utils import strip_tags
from urlparse import urlparse
from zExceptions import BadRequest
from zope.interface import classProvides
from zope.interface import implements

import csv
import os.path


csv_options = dict(dialect='excel-tab', doublequote=False, escapechar='\\')
KNOWN_POST_TYPES = ('post', 'page', 'attachment', 'revision')


def _skip(row, skip):
    """Test if we will need to skip row processing by dealing with the
    following cases:

    - parsing errors
    - items with revision type
    - items with draft status
    - explicit request

    :param row: [required] row to be analized
    :type row: dictionary
    :param skip: [required] list of item ID to be explicitly skiped
    :type skip: list
    :returns: True if we will skip the row
    :rtype: bool
    """
    if row['ID'] in skip:
        logger.info('Skipping row ID: ' + row['ID'])
        return True
    elif len(row) != 23 and 'publish' in row.values():
        logger.warn('Parsing error on row ID: ' + row['ID'])
        return True
    elif row['post_type'] not in KNOWN_POST_TYPES:
        logger.warn('Parsing error on row ID: ' + row['ID'])
        return True
    elif row['post_type'] == 'revision':
        logger.debug('Revision type on row ID: ' + row['ID'])
        return True
    elif row['post_status'] == 'draft':
        logger.debug('Draft status on row ID: ' + row['ID'])
        return True

    return False


def _get_path(id, post_type, category, date):
    """Return the path to the item; this will be used to create the
    object and its containers if needed.

    :param id: [required] id of the post
    :type id: string
    :param post_type: [required] WordPress post type
    :type post_type: string
    :param category: [required] slug of the category
    :type category: string
    :param date: [required] creation date
    :type date: DateTime
    :returns: path to the object starting from the root of the site
    :rtype: string
    :raises: zExceptions.BadRequest
    """
    if bad_id(id) is not None:
        raise BadRequest

    if post_type != 'attachment':
        # for posts and pages we need to contruct the path
        # according to the permalink structure:
        # "/%category%/%year%/%monthnum%/%day%/%postname%/"
        permalink_structure = '/{0}/{1}/{2}'.format(
            category, date.Date(), id)
    else:
        # for attachments we use the default location:
        # "/wp-content/uploads/%year%/%monthnum%/"
        permalink_structure = '/wp-content/uploads/{0}/{1}'.format(
            date.Date()[:-3], id)

    return permalink_structure


class CSVSource(object):

    """Blueprint section to import from a CSV export."""

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.source = options.get('source')
        self.portal_type = options.get('type')
        self.field_size_limit = int(options.get('field-size-limit', '131072'))
        self.skip = options.get('skip', '').replace(' ', '').split(',')
        self.display_names = get_display_names(self.source)
        self.taxonomies = get_taxonomies(self.source)

    def __iter__(self):
        for item in self.previous:
            yield item

        filename = os.path.join(self.source, 'wp_posts.csv')
        assert os.path.isfile(filename), 'Missing file: ' + filename

        with open(filename) as csvfile:
            csv.field_size_limit(self.field_size_limit)
            reader = csv.DictReader(csvfile, **csv_options)
            for row in reader:

                if _skip(row, self.skip):  # should we process this row?
                    continue

                item = dict()
                post_type = row['post_type']

                if post_type == 'post':
                    # posts are imported as portal_type
                    item['portal_type'] = self.portal_type
                elif post_type == 'page':
                    # pages are imported as Page
                    item['portal_type'] = 'Page'
                elif post_type == 'attachment':
                    # attachments are imported as Image or File
                    is_image = row['post_mime_type'].startswith('image')
                    item['portal_type'] = 'Image' if is_image else 'File'
                    item['_mimetype'] = row['post_mime_type']
                    item['_guid'] = row['guid']  # store for later

                if post_type != 'attachment':
                    # for posts and pages the id is the post name
                    item_id = row['post_name']
                    # Zope ids need to be ASCII
                    item_id = fix_id(item_id)
                    item['title'] = strip_tags(row['post_title'])
                else:
                    # for attachments we need to parse the guid
                    # and use the file name as title
                    url = urlparse(row['guid'])
                    item_id = item['title'] = url.path.split('/')[-1]
                    item_id = fix_id(item_id)

                try:
                    category, tags = self.taxonomies[row['ID']]
                except KeyError:
                    # files defining taxonomies are probably outdated
                    logger.warn('No taxonomies found for row ID: ' + row['ID'])
                    continue

                # WordPress stores only publication and modification times
                item['effective_date'] = row['post_date']
                item['modification_date'] = row['post_modified']
                # we use publication date as creation date
                item['creation_date'] = item['effective_date']
                date = DateTime(item['creation_date'])

                try:
                    item['_path'] = _get_path(item_id, post_type, category, date)
                except BadRequest:
                    logger.warn('Invalid object id on row ID: ' + row['ID'])
                    continue

                item['description'] = row['post_excerpt']

                # quotes are escaped; we need to fix that
                item['text'] = row['post_content'].replace('\\"', '"')
                # TODO: validate HTML to avoid post-processing surprises

                # use display_name instead of author_id, if match found
                author_id = row['post_author']
                item['creators'] = self.display_names.get(author_id, author_id)

                if row['post_status'] == 'publish':
                    item['_transitions'] = 'publish'

                item['_pinged'] = row['pinged']  # store for later

                yield item
