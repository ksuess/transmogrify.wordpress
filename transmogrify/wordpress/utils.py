# -*- coding: utf-8 -*-
from HTMLParser import HTMLParser
from plone.i18n.normalizer.interfaces import IIDNormalizer
from Products.CMFPlone.utils import safe_unicode
from urllib import unquote_plus
from zope.component import getUtility


class MLStripper(HTMLParser):

    """Taken from: http://stackoverflow.com/a/925630/644075

    Why don't you use RegEx? http://stackoverflow.com/a/1732454/644075
    """

    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    """Remove HTML tags from a string."""
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def fix_id(item_id):
    """Unquote plus and remove accents from ids."""
    item_id = unquote_plus(item_id)
    item_id = safe_unicode(item_id)
    id_normalizer = getUtility(IIDNormalizer)
    item_id = id_normalizer.normalize(item_id)
    return item_id
