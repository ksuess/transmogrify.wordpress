# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from plone.dexterity.interfaces import IDexterityContent
from requests.exceptions import ConnectionError
from requests.exceptions import RequestException
from transmogrify.wordpress.logger import logger
from zope.interface import classProvides
from zope.interface import implements

import logging
import requests


def set_logging_level(level):
    """Set requests module logging level."""
    levels = dict(error=logging.ERROR, info=logging.INFO, debug=logging.DEBUG)
    if level not in levels:
        return
    logging.getLogger('requests').setLevel(levels[level])


class FetchAttachment(object):

    """Blueprint section to fetch attachments from their original location."""

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        level = options.get('log-level', 'error').lower()
        set_logging_level(level)

    def __iter__(self):
        fetch_errors = []  # record all errors

        for item in self.previous:
            if '_guid' not in item:
                yield item
                continue

            url = item['_guid']
            path = item['_path']  # TODO: read path key from options

            if not path:  # not enough information
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                path.encode().lstrip('/'), None)


            # if object exists we will try to avoid downloading it again
            if obj is not None:

                if obj.portal_type not in ('File', 'Image'):  # not an attachment
                    yield item
                    continue

                # request only the header to check it
                try:
                    r = requests.head(url)
                except ConnectionError:  # skip on connection error
                    fetch_errors.append(url)
                    yield item
                    continue

                # content-length header could be missing if remote web
                # server is misconfigured for some mime types
                size = int(r.headers.get('content-length', 0))
                if IDexterityContent.providedBy(obj):
                    objsize = obj.get_size()
                else:  # Archetypes
                    objsize = obj.size()

                if size == objsize:  # already downloaded it
                    yield item
                    continue

            try:
                r = requests.get(url)
            except RequestException:  # skip on timeouts and other errors
                fetch_errors.append(url)
                yield item
                continue

            if r.status_code != 200:  # log error and skip item
                fetch_errors.append(url)
                msg = 'Error {0} when fetching {1}'.format(r.status_code, url)
                logger.warn(msg)
                yield item
                continue

            item['_data'] = r.content

            yield item

        # TODO: save fetch error report
