# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from plone.app.linkintegrity.handlers import modifiedArchetype
from plone.app.linkintegrity.handlers import modifiedDexterity
from plone.app.textfield.value import RichTextValue
from plone.dexterity.interfaces import IDexterityContent
from Products.Archetypes.interfaces import IBaseObject
from transmogrify.wordpress.logger import logger
from transmogrify.wordpress.utils import fix_id
from urlparse import urlparse
from zope.interface import classProvides
from zope.interface import implements

import itertools
import re

# This regex look for <img> or <a> tags and break the text into 3 parts
# isolating the src or href attribute content to update
URL_RE = re.compile(
    r'(<(?:img|a).*?(?:src|href)=")(.*?)(".*?>)', re.IGNORECASE | re.DOTALL)


class ResolveUID(object):

    """Blueprint section to replace internal links with UID."""

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.key = options.get('key', 'text')
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

            if self.key not in item:  # not enough info
                continue

            html = item[self.key]
            # Parse text with regex and call resolve_uid method
            # to fix for every URL
            html = URL_RE.sub(self.resolve_uid, html)

            # Create Rich Text value to update content field
            value = RichTextValue(html, 'text/html', 'text/html')

            # Update object value
            setattr(obj, self.key, value)

            # XXX: this seems to be very expensive
            # Update linkintegrity references
            if IBaseObject.providedBy(obj):
                modifiedArchetype(obj, event=None)
            elif IDexterityContent.providedBy(obj):
                modifiedDexterity(obj, event=None)

    def resolve_uid(self, x):
        """Parse HTML and update with URLs pointing to Plone objects.
        ex. url: "http://worpress.com/wp-content/uploads/2010/04/image.jpg"
        becomes: "resolveuid/c82a53270c904cfbbfd1a0d4cef90676"

        :param x: [required] Parsed Regex
        :type x: type Regex Match object
        :returns: the tag with an internal url
        :rtype: str
        """
        start = x.group(1)  # Start of tag ex.: '<img src="'
        url = x.group(2)  # URL
        end = x.group(3)  # End of tag ex.: '" />'

        url = fix_id(url)
        o = urlparse(url)

        internal_url = o.netloc == self.domain
        is_site_root = o.path == '' or o.path == '/'

        # links to external URL or to site root are ignored
        if not internal_url or is_site_root:
            return x.group(0)  # return unchanged

        path = str(o.path).strip(' ').lstrip('/')
        obj = traverse(self.context, path, None)

        if obj is None:  # object not found
            logger.warn('Could not resolve UUID: {0}'.format(url))
            return x.group(0)  # return unchanged

        # Create internal URL
        uuid = obj.UID()
        return '{0}resolveuid/{1}{2}'.format(start, uuid, end)
