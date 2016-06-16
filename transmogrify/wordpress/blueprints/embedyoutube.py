# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from transmogrify.wordpress.logger import logger
from zope.interface import classProvides
from zope.interface import implements

import re

YOUTUBE_RE = re.compile(r'\[youtube.*?id=[\\"]+(.*?)[\\"]+\.*?]', re.IGNORECASE | re.DOTALL)


class EmbedYoutube(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.key = options.get('key', 'text')

    def __iter__(self):
        for item in self.previous:
            if self.key in item:
                item[self.key] = self.fix_youtube(item[self.key])
            yield item

    def fix_youtube(self, html):
        """Parse HTML to look for youtube pseudo-tags and replace it
        with iframe tag inserting the youtube video.

        :param html: [required] html to be parsed
        :type html: str
        :returns: the tag with an internal url
        :rtype: str
        """
        if isinstance(html, unicode):
            html = html.encode('utf8')
        html = YOUTUBE_RE.sub(self.embed_youtube, html)
        return html

    def embed_youtube(self, x):
        """Parse HTML to look for youtube pseudo-tags and replace it
        with iframe tag inserting the youtube video.

        :param x: [required] Parsed Regex
        :type x: type Regex Match object
        :returns: the youtube frame tag
        :rtype: str
        """
        youtube_id = x.group(1)

        logger.info('Embedding youtube video %s' % youtube_id)

        return '<iframe src="https://www.youtube.com/embed/{0}"></iframe>'.format(
            youtube_id
        )
