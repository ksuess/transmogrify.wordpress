# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from collective.transmogrifier.utils import Condition
from zope.interface import classProvides
from zope.interface import implements


class DefaultView(object):

    """Blueprint section to set the default view of an item."""

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.view = options.get('view')
        condition = options.get('condition', 'python:True')
        self.condition = Condition(condition, transmogrifier, name, options)

    def __iter__(self):
        for item in self.previous:

            pathkey = self.pathkey(*item.keys())[0]
            if not pathkey:  # not enough info
                yield item
                continue
            path = item[pathkey]

            obj = traverse(self.context, str(path).lstrip('/'), None)
            if obj is None:  # object not found
                yield item
                continue

            if self.condition(item):
                obj.setLayout(self.view)

            yield item
