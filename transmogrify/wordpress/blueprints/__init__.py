# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from DateTime import DateTime
from lxml import etree, cssselect, html
from OFS.Image import File
from plone.app.discussion.interfaces import IConversation
from plone.outputfilters.filters.resolveuid_and_caption import ResolveUIDAndCaptionFilter
from Products.CMFPlone.utils import safe_unicode
from StringIO import StringIO
from urllib import unquote_plus
from urlparse import urlsplit
from zope.component import createObject
from zope.interface import classProvides, implements

import logging
import phpserialize
import re
import requests


logger = logging.getLogger('transmogrify.wordpress')

# XML namespaces
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'
DC = '{http://purl.org/dc/elements/1.1/}'
WP = '{http://wordpress.org/export/1.2/}'


def get_meta_values_by_key(node, meta_key):
    for postmeta in node.iterfind(WP + 'postmeta'):
        if postmeta.find(WP + 'meta_key').text == meta_key:
            yield postmeta.find(WP + 'meta_value').text



class WXRSource(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.filename = options['filename']
        self.portal_type = options['type']
        self.path = options['path']
        comment_option = options.get('import-comments', '')
        true_options = ('t', 'y', 'true', 'yes')
        self.include_comments = bool(comment_option.lower() in true_options)

    def __iter__(self):
        for item in self.previous:
            yield item

        file = open(self.filename, 'rb')
        i = 0
        self.wp_base_site_url = self.wp_base_blog_url = None
        self.author = {}
        for event, node in etree.iterparse(self.filename):
            # extract the base site and blog urls for later comparison
            if not (self.wp_base_site_url and self.wp_base_blog_url):
                # keep searching for these values so we can include them in
                # each item
                if node.tag == WP + 'base_site_url':
                    self.wp_base_site_url = node.text
                if node.tag == WP + 'base_blog_url':
                    self.wp_base_blog_url = node.text

            if node.tag == WP + 'author':
                adn = node.findtext(WP + 'author_display_name')
                al = node.findtext(WP + 'author_login')
                self.author[al] = adn

            # workaround for bug in lxml < 3.2.2
            # (see https://bugs.launchpad.net/lxml/+bug/1185701)
            if node.tag != 'item':
                if node.getparent() is None:
                    break
                else:
                    continue

            i += 1
            item = dict()

            item['portal_type'] = self.portal_type
            item_id = node.findtext(WP + 'post_name')
            # Zope ids need to be ASCII
            item_id = unquote_plus(item_id)\
                .decode('utf8').encode('ascii', 'ignore')
            path = '/'.join([self.path, item_id])
            item['_path'] = path
            item['_orig_url'] = node.findtext('link')

            if self.wp_base_site_url:
                item['_base_site_url'] = self.wp_base_site_url
            if self.wp_base_blog_url:
                item['_base_blog_url'] = self.wp_base_blog_url

            logger.info('Importing %s' % path)

            # capture media enclosures in item for later use
            item['_postmeta_enclosures'] = self.extract_media_enclosures(node)
            # capture disqus thread ids for posts with disqus comments
            #   the value passed might be None, so the import pipeline
            #   section for this should be primed to ignore that value
            item['_disqus_thread_id'] = self.extract_disqus_thread_id(node)
            # capture image attachments as represented by the 'Image' postmeta
            # key.  Ensure that the image urls are unique so we don't download
            # any of them more than once.
            item['_postmeta_images'] = self.extract_postmeta_images(node)
            # capture wordpress attachments as represented by the
            # 'wp:attachment_url' tag and associated post metadata
            item['_wordpress_attachments'] = self.extract_wp_attachments(node)

            item['title'] = node.findtext('title')
            item['description'] = node.findtext('description')
            item['creation_date'] = node.findtext('pubDate')
            item['effectiveDate'] = item['creation_date']
            item['modification_date'] = item['creation_date']
            item['creators'] = [node.findtext(DC + 'creator')]
            item['author_login'] = item['creators'][0]
            item['author_display_name'] = self.author[item['author_login']]

            tags = set([])
            for category in node.iterfind('category'):
                tags.add(category.text)
            item['subject'] = sorted(tags)

            item['text'] = node.findtext(CONTENT + 'encoded')

            status = node.findtext(WP + 'status')
            if status == 'publish':
                item['_transitions'] = 'publish'

            yield item

            # comments
            if self.include_comments:
                by_comment_id = lambda x: x.findtext(WP + 'comment_id')
                for cmt in sorted(node.iterfind(WP + 'comment'),
                                  key=by_comment_id):
                    # skip spam/unapproved comments
                    if cmt.findtext(WP + 'comment_approved') != '1':
                        continue

                    text = safe_unicode(cmt.findtext(WP + 'comment_content'))
                    author_name = cmt.findtext(WP + 'comment_author')
                    # add link to pingbacks
                    if cmt.findtext(WP + 'comment_type') == 'pingback':
                        url = cmt.findtext(WP + 'comment_author_url')
                        text = u'<a href="%s">%s</a>' % (url, text)
                        author_name = None

                    item = {
                        'portal_type': 'plone.Comment',
                        '_path': path,  # path to parent object
                        '_comment_id': int(cmt.findtext(WP + 'comment_id')),
                        '_in_reply_to': int(cmt.findtext(WP + 'comment_parent')),
                        'author_name': author_name,
                        'author_email': cmt.findtext(WP + 'comment_author_email'),
                        'created': cmt.findtext(WP + 'comment_date'),
                        'text': cmt.findtext(WP + 'comment_content'),
                    }

                    yield item

                    cmt.clear()

                node.clear()

        file.close()

    def extract_media_enclosures(self, node):
        """If the node has wp:postmeta 'enclosure' tags, preserve the content as media files.
        """
        # XXX: this is fairly naive, assuming that all enclosures contain
        #      a three-value meta_value, consisiting of the item url, size and
        #      mimetype
        enclosures = []
        enclosure_keys = ['url', 'size', 'mimetype']
        for enclosure in get_meta_values_by_key(node, 'enclosure'):
            enclosure_values = enclosure.split()
            enclosures.append(dict(zip(enclosure_keys, enclosure_values)))
        return enclosures

    def extract_disqus_thread_id(self, node):
        possible = tuple(get_meta_values_by_key(node, 'dsq_thread_id'))
        if len(possible) > 0:
            return possible[0]

    def extract_postmeta_images(self, node):
        """get a tuple of all the images named in postmeta, in order

        because the images are sometimes repeated, get unique, but still in
        order of presence in the wxr file
        """
        images = set()
        order = []
        for image_url in get_meta_values_by_key(node, 'Image'):
            images.add(image_url)
            order.append(image_url)
        return sorted(tuple(images), key=lambda x: order.index(x))

    def extract_wp_attachments(self, node):
        attachments = []
        for attachment_url in node.iterfind(WP + 'attachment_url'):
            attachment = dict(url=attachment_url.text, files=[], metadata=[],
                              backups=[])
            for filename in get_meta_values_by_key(node, '_wp_attached_file'):
                attachment['files'].append(filename)
            for metadata in get_meta_values_by_key(node, '_wp_attachment_metadata'):
                attachment['metadata'].append(phpserialize.loads(metadata))
            for bkp in get_meta_values_by_key(node, '_wp_attachment_backup_sizes'):
                attachment['backups'].append(phpserialize.loads(bkp))
            attachments.append(attachment)
        return attachments


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
    CAPTION_RE = re.compile(r'\[/?caption.*?\]', re.IGNORECASE | re.DOTALL)
    def cleanup_text(self, text):
        # - encode if necessary
        # - normalize newlines
        # - replace double-newlines with paragraph tags
        # - replace single newlines with linebreak tags
        # - remove custom caption tag
        if isinstance(text, unicode):
            text = text.encode('utf8')
        text = self.PRE_RE.sub(lambda x: x.group(1).replace('\r\n\r\n', '\n\n'), text)
        text = text.replace('\r\n\r\n', '<p>').replace('\r\n','\n').replace('\n', '<br />\n')
        text = self.CAPTION_RE.sub('', text)
        return text

        # TODO: handle [googlevideo] links, [gallery], [caption], others?


def safe_urlopen(url):
    try:
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:63.0) Gecko/20100101 Firefox/63.0'
        headers = {'User-Agent': user_agent}
        r = requests.get(url, headers=headers)
        return r
    except Exception as e:
        logger.error(u'safe_urlopen {0} {1}'.format(e, url))


class HTMLFetcher(object):
    """Parse HTML for images and inject them into the pipeline.

    so that they can be served locally.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.options = options
        self.previous = previous
        self.url_key = options.get('url_key', '_orig_url')
        self.target_key = options.get('target_key', 'text')
        self.selector = options.get('selector', 'div.entry')

    def __iter__(self):
        for item in self.previous:
            if self.url_key in item:
                url = item[self.url_key]
                res = safe_urlopen(url)
                if res is not None:
                    page = res.text
                    tree = etree.parse(StringIO(page), etree.HTMLParser())
                    selector = cssselect.CSSSelector(self.selector)
                    text = ''.join([html.tostring(n) for n in tree.xpath(selector.path)[0]]).encode('utf8')
                    item[self.target_key] = text

            yield item


class ImageMungingParser(ResolveUIDAndCaptionFilter):

    def __init__(self, site_path, base_path='/images'):
        ResolveUIDAndCaptionFilter.__init__(self)
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
                    # image in a link
                    # check if the link points to another image
                    href = self.atag['href']
                    res = safe_urlopen(href)
                    if res is not None:
                        mimetype = res.headers['content-type']
                        if 'image/' in mimetype:
                            src = href
                        else:
                            res = None

                if res is None:
                    res = safe_urlopen(src)
                    if res is not None:
                        mimetype = res.headers['content-type']

                if res is not None:
                    scheme, host, path, query, frag = urlsplit(src)
                    filename = path.split('/')[-1]
                    # Zope ids need to be ASCII
                    filename = unquote_plus(filename)\
                        .decode('utf8').encode('ascii', 'ignore')
                    data = res.content

                    # XXX choose scale size

                    # prepare image info
                    # for injection to transmogrifier pipeline

                    item = dict()

                    item['portal_type'] = 'Image'
                    path = '/'.join([self.base_path, filename])
                    # XXX avoid collisions
                    item['_path'] = path
                    logger.info('Importing %s' % path)

                    item['image'] = data

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
        return ResolveUIDAndCaptionFilter.unknown_endtag(self, tag)

    def append_tag(self, tag, attrs):
        strattrs = ''.join([' %s="%s"' % (key, value) for key, value in attrs])
        if tag in self.singleton_tags:
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

            for img in images:
                yield img


class WPPostmetaEnclosureSource(object):
    """download and insert into the pipeline any files referenced in 'enclosure'
    postmeta tags

    enclosures will be a list of dicts with the keys 'url', 'size' and
    'mimetype'
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.options = options
        self.previous = previous
        self.enclosure_key = '_postmeta_enclosures'
        self.base_path = options.get('path', 'enclosures')
        self.site_path = '/'.join(transmogrifier.context.getPhysicalPath())

    def __iter__(self):
        for item in self.previous:
            # no enclosures, skip
            if self.enclosure_key not in item:
                yield item; continue

            # XXX: it would be good to add a relationship between enclosures
            # and the posts they are related to.  How might we do this?
            #
            item['_enclosure_internal_paths'] = []
            for enclosure in item[self.enclosure_key]:
                res = safe_urlopen(enclosure['url'])
                if res is not None:
                    scheme, host, path, query, frag = urlsplit(enclosure['url'])
                    filename = path.split('/')[-1]
                    # Zope ids need to be ASCII
                    filename = unquote_plus(filename)\
                        .decode('utf8').encode('ascii', 'ignore')
                    encl = dict()
                    if 'image' in enclosure['mimetype']:
                        encl['portal_type'] = 'Image'
                        item_key = 'image'
                    else:
                        encl['portal_type'] = 'File'
                        item_key = 'file'
                    data = res.content
                    path = '/'.join([self.base_path, filename])
                    # XXX avoid collisions
                    encl['_path'] = path
                    encl[item_key] = data
                    logger.info('Importing {0} {1} of {2}'.format(path, encl, item))
                    # add the location where this enclosure will be added
                    # to the list of internal enclosures.  We can use this
                    # later as a way of connecting the original item to the
                    # enclosure.
                    item['_enclosure_internal_paths'].append(path)
                    # yield the enclosure first so it will exist when the
                    # containing item is created.
                    yield encl

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
            if item[typekey] != 'plone.Comment':  # not a comment
                yield item
                continue

            pathkey = self.pathkey(*item.keys())[0]
            if not pathkey:  # not enough info
                yield item
                continue
            path = item[pathkey]

            ob = self.context.unrestrictedTraverse(path.lstrip('/'), None)
            if ob is None:
                yield item
                continue  # object not found

            # XXX make sure comment doesn't exist already?

            conversation = IConversation(ob)
            comment = createObject('plone.Comment')
            comment.text = item['text']
            comment.author_name = item['author_name']
            comment.author_email = item['author_email']
            comment.creation_date = DateTime(item['created']).asdatetime()
            comment.modification_date = comment.creation_date
            in_reply_to = item.get('_in_reply_to', 0)
            if in_reply_to:
                comment.in_reply_to = self.comment_map[in_reply_to]

            id = conversation.addComment(comment)
            self.comment_map[item['_comment_id']] = id

            yield item
