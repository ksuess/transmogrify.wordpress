Introduction
============

``transmogrify.wordpress`` provides a `collective.transmogrifier`_ pipeline
for importing a Wordpress blog into Plone.

.. _`collective.transmogrifier`: http://pypi.python.org/collective.transmogrifier

In particular, it is useful if you have a Wordpress export in WXR format, and
want to end up with a Plone-based blog using `Scrawl`_ and
`plone.app.discussion`_. (The complementary use of `collective.blog.star`_ for
additional blog functionality is recommended, but not required.)

.. _`Scrawl`: http://plone.org/products/scrawl
.. _`plone.app.discussion`: http://pypi.python.org/plone.app.discussion
.. _`collective.blog.star`: http://pypi.python.org/collective.blog.star

A WXR export of a Wordpress.com blog can be obtained via Tools -> Export in the
blog's dashboard.


Usage
=====

A sample pipeline, wordpress.cfg, is provided.  You can use it by editing it
in place to set a few variables at the top of the file, and then importing
the transmogrify.wordpress profile via portal_setup.

The following settings must be configured in the ``options`` part of
wordpress.cfg:

filename
  Full path to the Wordpress WXR export file.
path
  Path, relative to the site root, of the folder where blog entries should be
  created.
type
  The desired portal_type for blog entries.  Must be an Archetypes-based type
  with a 'text' field, and must already exist in the site.  The default,
  'Blog Entry', may be obtained by installing `Scrawl`_.
entry-selector
  CSS selector to find the body of the post within its original HTML page.
  (The body is fetched this way instead of using the one in the WXR,
  because the WXR contains special Wordpress markup.)


Other prerequisites:

* The importing of comments requires that `plone.app.discussion`_ is installed.

.. Note::
   The pipeline will take some time to run, and you'll probably get a timeout
   error unless you are accessing Zope directly with no proxy or web server in
   front. Even if this happens the import will continue to run. Progress is 
   logged to the Zope event log at the INFO level, so you can watch the log to  
   see what is happening.

Alternatively, you can copy the wordpress.cfg pipeline into your own package,
and edit and run it as part of your own GenericSetup profile by naming it in a
transmogrifier.txt file placed in the profile directory (see the
transmogrify.wordpress profile for an example of how this is done).


Caveats
=======

This importer is currently in an alpha state. Don't expect it to work perfectly
without a little coaxing.  Contributions to improve it are welcome.

* For now, the import can only create Archetypes-based content types. That
  could probably be changed with a little work.

* No effort is made to map between differing sets of usernames in Wordpress and
  Plone.

* Wordpress' "categories" and "tags" are lumped together as Plone "tags".

* Image sources are currently updated with path-based links even if the site is
  configured to link by UID.

* Height and width specified on image tags is left intact. No effort is made to
  choose the most reasonable scale size to download for the specified height and
  width.

* No effort has been made to make the pipeline do something reasonable if it
  is run more than once. In particular, comments will be re-added, and images
  will be re-fetched, even if they are already present in the site.

* No effort is made to make sure that the old Wordpress URLs will continue to
  work in the new site if the blog's domain is pointed at the new site. This
  can be handled via rewrites in something in front of Zope, such as Apache
  or nginx.

* Comments that are unapproved or marked as spam are not imported.

* Pingbacks are imported, but don't actually contain a link to the referring
  page, as plone.app.discussion doesn't support HTML in comments at this time.


Included Blueprints
===================

.. Note::
   This section contains advanced information on the components of the pipeline.

``transmogrify.wordpress`` makes use of several custom transmogrifier 
blueprints. Some of these would probably be useful in non-Wordpress-related
pipelines and should probably get factored out into separate packages.

transmogrify.wordpress.blueprints.wxrsource
-------------------------------------------

Parses a WXR-format export file and injects an item into the pipeline for each
blog post and comment.

Settings:

filename
  Path to the WXR file on disk.
path
  Path relative to the site root where blog posts should be imported.
type
  portal_type that should be used for imported blog posts.
import-comments
  you can choose to import wordpress comments.  defaults to false

Sets the following pipeline keys:

portal_type
  Value of the ``type`` setting for blog posts. ``plone.Comment`` for comments.
_orig_url
  The URL of the original blog post.
_path
  Path of the new item, based on the ``path`` setting and the Wordpress post_name.
  For comments, path of the item to which the comment should be added.
title
  Post title
description
  Post description
creation_date, effectiveDate, modification_date
  Wordpress creation date
creators
  Wordpress post author
subject
  A list of Wordpress categories and tags, sorted alphabetically
text
  The text of the blog post or comment. Unmodified from Wordpress' markup
  (so uses newlines instead of P and BR tags, among other things).
_transitions
  Set to 'publish' to control the workflow state later in the pipeline.
_comment_id
  For comments only, the unique Wordpress ID of the comment (used for threading).
_in_reply_to
  For comments only, the Wordpress ID of the comment's parent (used for threading).
author_name
  For comments only, name of the comment's author.
author_email
  For comments only, email of the comment's author.
created
  For comments only, date of the comment.


transmogrify.wordpress.blueprints.text_cleanup
----------------------------------------------

Cleans up Wordpress markup into more standard HTML.  In particular, it will:

* Encode the text if necessary
* Normalize carriage returns to newlines
* Replace double newlines with P tags
* Replace single newlines with BR tags

These operations are performed on the pipeline key named in the blueprint's
``key`` setting (defaults to "text").


transmogrify.wordpress.blueprints.fetch_html
--------------------------------------------

Fetches the content of an HTML page and selects a portion of it, which it
places (UTF8-encoded) into a pipeline key.

Settings:

url_key
  Name of the pipeline key which gives the URL to be fetched. (Default:
  ``_orig_url``.)
selector
  CSS selector specifying which portion of the retrieved page to retain.
target_key
  Name of the pipeline key where the fetched HTML should be stored.

If the url_key is not found for the current item, or the page cannot be
retrieved, no change will be made to the target key.


transmogrify.wordpress.blueprints.html_image_source
---------------------------------------------------

This blueprint parses HTML for images, fetches the images from their current
remote location, and injects new items into the pipeline so that those images
will be added to the Plone site. It also updates the ``src`` attribute of the
image tags so that they will refer to the new local images.

If an IMG tag is inside an A tag whose ``href`` points at another image, it is
assumed that the latter image is a larger version, and it is fetched instead
of the one referred to by the IMG's ``src`` attribute.

Settings:

key
  Name of the pipeline key which should be parsed for images, and updated.
  (Default: "text")
path
  Path relative to the site root of the container to which images should be
  added. (Default: "images")


transmogrify.wordpress.blueprints.set_mimetype
----------------------------------------------

Wraps text in a Zope File object with a particular mimetype, so that the
mimetype can be correctly transferred when the value is set on an item via
an Archetypes File or Text field mutator.

Settings:

key
  Name of the pipeline key which contains the text, and which should be
  replaced with the File object.
mimetype
  Mimetype that should be set. (Default: "text/html")


transmogrify.wordpress.blueprints.comment_constructor
-----------------------------------------------------

Constructs a plone.app.discussion comment, and adds it to the conversation for
a particular item.

Threading of comments is handled as long as the injection of comments into the
pipeline is ordered such that a comment's parent has always been already created.

Uses the following keys from the item in the pipeline:

portal_type
  Must be ``plone.Comment`` or the item will be skipped.
path
  Path to the item which is being commented on.
text
  Text of the comment (should be plain text).
author_name
  Name of the commenter.
author_email
  Email of the commenter.
created
  Date the comment was made.
_comment_id
  Source system's unique ID of this comment.
_in_reply_to
  Source system's unique ID of the parent of this comment. That comment must
  have already been added or things will fail. Defaults to '0', which means
  a top-level comment.


Credits
=======

``transmogrify.wordpress`` was created by David Glick for `Groundwire`_.

.. _`Groundwire`: http://groundwire.org
