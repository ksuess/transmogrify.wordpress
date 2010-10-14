import urllib2
from urlparse import urlsplit
import re
from lxml import etree
from urllib import unquote_plus
from zope.interface import classProvides, implements
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

from DateTime import DateTime
from zope.component import createObject
from plone.app.discussion.interfaces import IConversation
from Products.CMFPlone.utils import safe_unicode
from Products.TinyMCE.transforms.parser import TinyMCEOutput, singleton_tags

from StringIO import StringIO
from OFS.Image import File

import logging
logger = logging.getLogger('transmogrify.wordpress')

# XML namespaces
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'
DC = '{http://purl.org/dc/elements/1.1/}'
WP = '{http://wordpress.org/export/1.0/}'

class WXRSource(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.filename = options['filename']
        self.portal_type = options['type']
        self.path = options['path']

    def __iter__(self):
        for item in self.previous:
            yield item

        file = open(self.filename, 'rb')
        i = 0
        for event, node in etree.iterparse(file, tag='item'):
            i += 1
            item = dict()
            
            item['portal_type']   = self.portal_type
            item_id               = node.findtext(WP + 'post_name')
            # Zope ids need to be ASCII
            item_id = unquote_plus(item_id).decode('utf8').encode('ascii', 'ignore')
            path = '/'.join([self.path, item_id])
            item['_path']         = path
            logger.info('Importing %s' % path)
            
            item['title']         = node.findtext('title')
            item['description']   = node.findtext('description')
            item['creation_date'] = node.findtext('pubDate')
            item['effectiveDate'] = item['creation_date']
            item['modification_date'] = item['creation_date']
            item['creators']      = [node.findtext(DC + 'creator')]
            
            tags = set([])
            for category in node.iterfind('category'):
                tags.add(category.text)
            item['subject']       = sorted(tags)
            
            item['text']          = node.findtext(CONTENT + 'encoded')
            
            status                = node.findtext(WP + 'status')
            if status == 'publish':
                item['_transitions'] = 'publish'

            yield item
            
            # comments
            by_comment_id = lambda x: x.findtext(WP + 'comment_id')
            for node in sorted(node.iterfind(WP + 'comment'), key=by_comment_id):
                # skip spam/unapproved comments
                if node.findtext(WP + 'comment_approved') != '1':
                    continue
                
                text = safe_unicode(node.findtext(WP + 'comment_content'))
                author_name = node.findtext(WP + 'comment_author')
                # add link to pingbacks
                if node.findtext(WP + 'comment_type') == 'pingback':
                    url = node.findtext(WP + 'comment_author_url')
                    text = u'<a href="%s">%s</a>' % (url, text)
                    author_name = None
                
                item = dict()
                item['portal_type']  = 'plone.Comment'
                item['_path']        = path # path to parent object
                item['_comment_id']  = int(node.findtext(WP + 'comment_id'))
                item['_in_reply_to'] = int(node.findtext(WP + 'comment_parent'))
                item['author_name']  = author_name
                item['author_email'] = node.findtext(WP + 'comment_author_email')
                item['created']      = node.findtext(WP + 'comment_date')
                item['text']         = node.findtext(WP + 'comment_content')
                
                yield item
            
            # release memory
            node.clear()
            
        file.close()


class WordpressTextCleanupSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.key = options.get('key', 'text')

    def __iter__(self):
        for item in self.previous:
            if self.key in item:
                item[self.key] = self.cleanup_text(item[self.key])
            yield item

    PRE_RE = re.compile(r'(<pre>.*?</pre>)', re.IGNORECASE | re.DOTALL)
    def cleanup_text(self, text):
        # - encode if necessary
        # - normalize newlines
        # - replace double-newlines with paragraph tags
        # - replace single newlines with linebreak tags
        if isinstance(text, unicode):
            text = text.encode('utf8')
        text = self.PRE_RE.sub(lambda x: x.group(1).replace('\r\n\r\n', '\n\n'), text)
        text = text.replace('\r\n\r\n', '<p>').replace('\r\n','\n').replace('\n', '<br />\n')
        return text
        
        # TODO: handle [googlevideo] links, [gallery], [caption], others?


def safe_urlopen(url):
    try:
        return urllib2.urlopen(urllib2.Request(url))
    except urllib2.URLError:
        return None


class ImageMungingParser(TinyMCEOutput):
    
    def __init__(self, site_path, base_path='/images'):
        TinyMCEOutput.__init__(self)
        self.atag = None
        self.abuffer = []
        self.items = []
        self.site_path = site_path
        self.base_path = base_path
    
    def append_data(self, data, add_eol=0):
        if add_eol:
            data += '\n'
        if self.atag:
            self.abuffer.append(data)
        else:
            self.pieces.append(data)
    
    def unknown_starttag(self, tag, attrs):
        if tag in ['a', 'img']:
            attributes = {}
            for (key, value) in attrs:
                attributes[key] = value
        
            if tag == 'a':
                self.atag = attributes
            elif tag == 'img' and 'src' in attributes:
                src = attributes['src']
                res = None
                if self.atag and 'href' in self.atag:
                    # image in a link; check if the link points to another image
                    href = self.atag['href']
                    res = safe_urlopen(href)
                    if res is not None:
                        mimetype = res.info()['content-type']
                        if 'image/' in mimetype:
                            src = href
                        else:
                            res = None

                if res is None:
                    res = safe_urlopen(src)
                    if res is not None:
                        mimetype = res.info()['content-type']
                
                if res is not None:
                    scheme, host, path, query, frag = urlsplit(src)
                    filename = path.split('/')[-1]
                    # Zope ids need to be ASCII
                    filename = unquote_plus(filename).decode('utf8').encode('ascii', 'ignore')
                    # wrap the data so it'll get added with the correct filename & mimetype
                    data = File(filename, 'image', StringIO(res.read()), mimetype)
            
                    # XXX choose scale size
            
                    # prepare image info for injection to transmogrifier pipeline
            
                    item = dict()
            
                    item['portal_type']   = 'Image'
                    path = '/'.join([self.base_path, filename])
                    # XXX avoid collisions
                    item['_path']         = path
                    logger.info('Importing %s' % path)
            
                    item['image']         = data
            
                    self.items.append(item)
                    
                    # update src attribute
                    attributes['src'] = '/'.join([self.site_path, path])
                    if self.atag and 'href' in self.atag:
                        self.atag['href'] = '%s/image_view_fullscreen' % attributes['src']
                else:
                    # couldn't fetch image; leave src as is
                    logger.warn("Couldn't fetch image: %s" % src)
            
            attrs = attributes.iteritems()

        if tag != 'a':
            self.append_tag(tag, attrs)
    
    def unknown_endtag(self, tag):
        if tag == 'a':
            attrs = self.atag.items()
            self.atag = None
            self.append_tag('a', attrs)
            self.pieces.extend(self.abuffer)
            self.abuffer = []
        return TinyMCEOutput.unknown_endtag(self, tag)

    def append_tag(self, tag, attrs):
        strattrs = ''.join([' %s="%s"' % (key, value) for key, value in attrs])
        if tag in singleton_tags:
            self.append_data('<%s%s />' % (tag, strattrs))
        else:
            self.append_data('<%s%s>' % (tag, strattrs))


class HTMLImageSource(object):
    """
    Parse HTML for images and inject them into the pipeline so that they can
    be served locally.
    """
    classProvides(ISectionBlueprint)
    implements(ISection)
    
    def __init__(self, transmogrifier, name, options, previous):
        self.options = options
        self.previous = previous
        self.key = options.get('key', 'text')
        self.base_path = options.get('path', 'images')
        self.site_path = '/'.join(transmogrifier.context.getPhysicalPath())

    def __iter__(self):
        for item in self.previous:

            images = []
            if self.key in item:
                text = item[self.key]
                parser = ImageMungingParser(site_path=self.site_path, base_path=self.base_path)
                parser.feed(text)
                parser.close()
                item[self.key] = parser.getResult()
                images = parser.items

            yield item
            
            for item in images:
                yield item


class MimetypeSetter(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.mimetype = options.get('mimetype', 'text/html')
        self.key = options.get('key', 'text')

    def __iter__(self):
        for item in self.previous:
            if self.key in item:
                item[self.key] = File(self.key, self.key, StringIO(item[self.key]), self.mimetype)
            yield item


class CommentConstructor(object):
    classProvides(ISectionBlueprint)
    implements(ISection)
    
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.options = options
        self.context = transmogrifier.context
        self.typekey = defaultMatcher(options, 'type-key', name, 'type', 
                                      ('portal_type', 'Type'))
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.comment_map = {}

    def __iter__(self):
        for item in self.previous:
            keys = item.keys()
            typekey = self.typekey(*keys)[0]
            if item[typekey] != 'plone.Comment': # not a comment
                yield item; continue

            pathkey = self.pathkey(*item.keys())[0]
            if not pathkey: # not enough info
                yield item; continue
            path = item[pathkey]

            ob = self.context.unrestrictedTraverse(path.lstrip('/'), None)
            if ob is None:
                yield item; continue # object not found

            # XXX make sure comment doesn't exist already?

            conversation = IConversation(ob)
            comment = createObject('plone.Comment')
            comment.text              = item['text']
            comment.author_name       = item['author_name']
            comment.author_email      = item['author_email']
            comment.creation_date     = DateTime(item['created']).asdatetime()
            comment.modification_date = comment.creation_date
            in_reply_to = item.get('_in_reply_to', 0)
            if in_reply_to:
                comment.in_reply_to = self.comment_map[in_reply_to]

            id = conversation.addComment(comment)
            self.comment_map[item['_comment_id']] = id

            yield item
