# -*- coding: utf-8 -*-
from HTMLParser import HTMLParser
from Products.CMFPlone.utils import safe_unicode
from urllib import unquote_plus


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
    item_id = item_id.encode('ascii', 'ignore')
    return item_id
