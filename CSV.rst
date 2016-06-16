Introduction
============

This part of the documentation refers to the usage of the CSVSource blueprint section.

Prerequisites
=============

Export as CSV the following tables from your WordPress site usign the phpMyAdmin interface:

* wp_posts
* wp_term_relationships
* wp_term_taxonomy
* wp_terms
* wp_users

Use the following options for all:

* Fields terminated by '\\t'
* Remove CRLF characters within fields
* Put field names in the first row

For more information see: http://stackoverflow.com/a/31460534/644075

Importing polls
---------------

If you want to import polls created with the `WP-Polls`_ plugin you must use the `transmogrify.wppolls`_ package.

.. _`transmogrify.wppolls`: https://pypi.python.org/pypi/transmogrify.wppolls
.. _`WP-Polls`: https://wordpress.org/plugins/wp-polls/

Sections
========

transmogrify.wordpress.csvsource
--------------------------------

Currently this section only import posts, pages and attachments; comments are ignored.

A typical configuration for this section should be like this:

.. code-block:: ini

    [csvsource]
    blueprint = transmogrify.wordpress.csvsource
    source = /home/customer/site/data/
    type = collective.nitf.content
    skip = 146989

source:
    is the path where all CSV files are stored

type:
    is the content type to be used for blog posts;
    pages are imported as `Page` and attachment as `Image` or `File` depending on its mime type by using a `mimeencapsulator` section before the constructor:

.. code-block:: ini

    [mimeencapsulator]
    blueprint = plone.app.transmogrifier.mimeencapsulator
    mimetype = item/_mimetype
    field = python:'image' if item['portal_type'] == 'Image' else 'file'

skip:
    is a comma-separated list of posts to be explicitly ignored;
    this is useful if the body of the post contains illegal characters that lead to import errors

.. code-block:: ini

    [csvsource]
    blueprint = transmogrify.wordpress.csvsource
    ...
    skip = 146989,151344,151517

field-size-limit:
    an integer specifying the CSV field size limit;
    this is useful to avoid `Error: field larger than field limit (131072)`.
    If you're getting into this issue use the following command and set the value to an integer larger that the number returned:

.. code-block:: bash

    # wc -L wp_posts.csv
    687948 wp_posts.csv

.. code-block:: ini

    [csvsource]
    blueprint = transmogrify.wordpress.csvsource
    ...
    field-size-limit = 700000

transmogrify.wordpress.fetchattachment
--------------------------------------

Fetches attachments from the original site by requesting the content and setting the `_data` field of the item.
If the item already has data and the size of it is equal to the size of the remote object, it will be skipped assuming both are the same.
If a status code different from `200` is received, the item is skipped and a warning message is logged.

.. code-block:: ini

    [fetchattachment]
    blueprint = transmogrify.wordpress.fetchattachment
    log-level = error

log-level:
    sets the log level to one of the following options: 'error', 'info' or 'debug'

TODO: add caching feature

transmogrify.wordpress.embedyoutube
-----------------------------------

Replace youtube pseudo-tag `[youtube id="NwTxjNhGpOM"]` with an iframe embedding youtube video into document.

.. code-block:: ini

    [embedyoutube]
    blueprint = transmogrify.wordpress.youtube

transmogrify.wordpress.defaultview
----------------------------------

Sets the default view of a content item.
You can specify an optional ``condition`` option;
if given, the view is only changed when the condition, which is a TALES expression, is true.

.. code-block:: ini

    [defaultview]
    blueprint = transmogrify.wordpress.defaultview
    view = text_only_view
    condition = python:item.get('portal_type') == 'collective.nitf.content'

transmogrify.wordpress.resolveuid
---------------------------------

It is a post processing section that fixes internal links;
It replaces paths with internal links (those that refer to the same domain we're importing), with calls to `resolveuid`.
Also, updates the reference catalog so we can search for references, and take care of site integrity.

.. code-block:: ini

    [resolveuid]
    blueprint = transmogrify.wordpress.resolveuid
    type = collective.nitf.content
    domain = wordpress.com

type:
    data type we are looking to fix urls.

domain:
    domain name of the site we're importing;
    this is used to specify links that are going to be treated as internal.

transmogrify.wordpress.relatecontent
------------------------------------

It is a post processing section that add related items into objects;
It looks for wordpress `pinged` column and add internal urls as related content (if imported).

.. code-block:: ini

    [relatecontent]
    blueprint = transmogrify.wordpress.relatecontent
    domain = wordpress.com

domain:
    domain name of the site we're importing;
    this is used to specify links that are going to be treated as internal.

transmogrify.wordpress.moveattachment
-------------------------------------

It is a post processing section that moves images and files into the specified container type;
It looks for the reference catalog and checks if an attachment is referenced only by one object of the specified type.
This pipeline section must be placed after resolveuid, where those references are updated.

.. code-block:: ini

    [moveattachment]
    blueprint = transmogrify.wordpress.moveattachment
    type = collective.nitf.content

type:
    container data type we are moving images and files into.
