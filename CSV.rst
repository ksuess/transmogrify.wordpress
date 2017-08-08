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

Installation
============

Add ``transmogrify.wordpress`` to your buildout ``eggs`` and ``zcml`` directives:

.. code-block:: ini

    [buildout]
    ...
    eggs =
        ...
        transmogrify.wordpress
    zcml =
        ...
        transmogrify.wordpress

Create a transmogrifier pipeline including all sections that must be run to import the content.
A typical pipeline is generally complex and could look like this one:

.. code-block:: ini

    [transmogrifier]
    pipeline =
        csvsource
        fetchattachment
        mimeencapsulator
        folders
        insert_transition
        constructor
        text_cleanup
        atschemaupdater
        schemaupdater
        datesupdater
        embedyoutube
        defaultview
        resolveuid
        relatecontent
        moveattachment
        workflowupdater
        reindexobject
        savepoint
        logger

    [csvsource]
    blueprint = transmogrify.wordpress.csvsource
    source =
    type = collective.nitf.content
    skip = 146989,151344,151517
    field-size-limit = 700000

    [fetchattachment]
    blueprint = transmogrify.wordpress.fetchattachment

    [mimeencapsulator]
    blueprint = plone.app.transmogrifier.mimeencapsulator
    mimetype = item/_mimetype
    field = python:'image' if item['portal_type'] == 'Image' else 'file'

    [folders]
    blueprint = collective.transmogrifier.sections.folders

    [insert_transition]
    blueprint = collective.transmogrifier.sections.inserter
    key = string:_transitions
    value = string:publish
    condition = python:item.get('_type') == 'Folder'

    [constructor]
    blueprint = collective.transmogrifier.sections.constructor

    [text_cleanup]
    blueprint = transmogrify.wordpress.blueprints.text_cleanup
    key = text

    [atschemaupdater]
    blueprint = plone.app.transmogrifier.atschemaupdater

    [schemaupdater]
    blueprint = transmogrify.dexterity.schemaupdater

    [datesupdater]
    blueprint = plone.app.transmogrifier.datesupdater

    [embedyoutube]
    blueprint = transmogrify.wordpress.embedyoutube

    [defaultview]
    blueprint = transmogrify.wordpress.defaultview
    view = text_only_view
    condition = python:item.get('portal_type') == 'collective.nitf.content'

    [resolveuid]
    blueprint = transmogrify.wordpress.resolveuid
    type = collective.nitf.content
    domain = www.conversaafiada.com.br

    [relatecontent]
    blueprint = transmogrify.wordpress.relatecontent
    domain = www.conversaafiada.com.br

    [moveattachment]
    blueprint = transmogrify.wordpress.moveattachment
    type = collective.nitf.content

    [workflowupdater]
    blueprint = plone.app.transmogrifier.workflowupdater

    [reindexobject]
    blueprint = plone.app.transmogrifier.reindexobject

    [savepoint]
    blueprint = collective.transmogrifier.sections.savepoint
    every = 100

    [logger]
    blueprint = collective.transmogrifier.sections.logger
    name = WordPress
    level = INFO
    key = _path

The core of the transmogrify process is the ``csvsource`` section, as it will serve as a source of all the information to import the WordPress site.

The ``fetchattachment`` section takes care of importing file and image attachments;
this section will fetch those static files from the site we're importing in real time.
That means the site we're importing must be accessible from the computer running the transmogrifier process.

The ``mimeencapsulator`` section is a helper to decide what kind of content type will be created using the fetched attachment.

The ``folders`` section will create the site structure.
The ``insert_transition`` section is a helper to publish the site structure created on the previous section.

The ``constructor`` sections takes care of creating all content types instances.

The ``text_cleanup`` section is used to remove some WordPress sppecific patterns on text fields, like the usage of newline characters instead of ``<p>`` and ``<br>`` tags.
It will also remove custom caption tags and encode the text, if necessary.

The ``atschemaupdater`` and ``schemaupdater`` sections takes care of updating the content type instance schemas.
You can use the later only in case you site uses Dexterity-based content types only.

The ``datesupdater`` section will set the right creation and modification time on the content type instances.

The ``embedyoutube`` section is replaces to youtube pseudo-tags and replace with <iframe> tags refering to YouTube videos.

The ``defaultview`` section can be used in case you want to set a default view different from ``view``.

``resolveuid`` and ``relatecontent`` are post-processing sections that run after the import process has finished.

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
