# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from Products.Archetypes.interfaces import IBaseObject
from Products.Archetypes.interfaces import IReferenceable
from zope.interface import classProvides
from zope.interface import implements

import itertools


class MoveAttachment(object):

    """Blueprint section to move attachments inside a container, if
    they are referenced only by it.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.portal_type = options.get('type')

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

            # XXX: is there an interface provided by both?
            if obj.portal_type not in ('Image', 'File'):
                continue

            references = []
            if IBaseObject.providedBy(obj):
                references = obj.getBackReferences()
            elif IDexterityContent.providedBy(obj):
                adapted = IReferenceable(obj)
                references = adapted.getBackReferences()
            if len(references) != 1:
                continue

            # Move attachment into container
            if references[0].portal_type == self.portal_type:
                api.content.move(source=obj, target=references[0])
