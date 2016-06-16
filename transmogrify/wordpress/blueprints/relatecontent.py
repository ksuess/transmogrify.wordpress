# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from transmogrify.wordpress.logger import logger
from transmogrify.wordpress.utils import fix_id
from urlparse import urlparse
from z3c.relationfield import RelationValue
from zope.component import getUtility
from zope.interface import classProvides
from zope.interface import implements
from zope.intid.interfaces import IIntIds

import itertools


class RelateContent(object):

    """Blueprint section to add related items."""

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.domain = options.get('domain', 'wordpress.com')

        self.seen = []  # list of objects already processed

    def __iter__(self):
        # keep a copy of previous generator to post-process items
        self.previous, self.postprocess = itertools.tee(self.previous)

        for item in self.previous:
            yield item

        for item in self.postprocess:
            pathkey = self.pathkey(*item.keys())[0]
            if not pathkey:  # not enough info
                continue
            path = item[pathkey]

            obj = traverse(self.context, str(path).lstrip('/'), None)
            if obj is None:  # object not found
                continue

            self.add_related_content(obj, item)

    def add_related_content(self, obj, item):
        """Look into WordPress list of related content and create Plone
        related content list.

        :param obj: [required] object to add related content
        :type obj: type constructor parameter
        :param item: [required] transmogrify item
        :type item: dict
        """
        # Get the string with URLs from related content
        pinged = item.get('_pinged', '')
        if pinged == '':
            return  # No related content

        # The URL is formated with multiple URLs together without
        # separator.  To break it into a list, I need to split on
        # http and reconstruct the url
        # TODO: handle HTTPS scheme
        related_urls = set('http{0}'.format(url.rstrip('/'))
                           for url in pinged.split('http')[1:])

        # Create a list of related items to update object's field
        related_items = []
        for url in related_urls:
            # Parse URL and check domain
            url = fix_id(url)
            o = urlparse(url)
            if o.netloc != self.domain:
                continue

            path = str(o.path).strip(' ').lstrip('/')
            related_obj = traverse(self.context, path, None)

            if related_obj is None:  # object not found
                logger.warn('Broken link: {0}'.format(url))
                continue

            # Get related item ID
            intids = getUtility(IIntIds)
            to_id = intids.getId(related_obj)
            related_items.append(RelationValue(to_id))

        # No related content
        if len(related_items) == 0:
            return

        obj.relatedItems = related_items
