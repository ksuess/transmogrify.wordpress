# -*- coding: utf-8 -*-
from collections import namedtuple
from transmogrify.wordpress.logger import logger

import csv
import os.path


def get_display_names(source):
    """Return a mapping between a user ID and its display name.

    :param source: [required] path to wp_users.csv file
    :type obj: string
    :returns:  the display_name of each user
    :rtype: dictionary
    """
    logger.info('Parsing "wp_users.csv" file')
    filename = os.path.join(source, 'wp_users.csv')
    assert os.path.isfile(filename), 'Missing file: ' + filename

    mapping = dict()
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel-tab')
        for row in reader:
            mapping[row['ID']] = row['display_name']

    return mapping


def read_term_relationships(source):
    """Extract term relationships from a CVS file.

    :param source: [required] path to wp_term_relationships.csv file
    :type obj: string
    :returns:  the term taxonomies related with each object
    :rtype: dictionary of lists
    """
    logger.info('Parsing "wp_term_relationships.csv" file')
    filename = os.path.join(source, 'wp_term_relationships.csv')
    assert os.path.isfile(filename), 'Missing wp_term_relationships.csv file'

    mapping = dict()
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel-tab')
        for row in reader:
            if row['object_id'] not in mapping:
                mapping[row['object_id']] = [row['term_taxonomy_id']]
            else:
                mapping[row['object_id']].append(row['term_taxonomy_id'])

    return mapping


def read_term_taxonomy(source):
    """Extract term taxonomies from a CVS file.

    :param source: [required] path to wp_term_taxonomy.csv file
    :type obj: string
    :returns:  the term id and taxonomy related with each term taxonomy
    :rtype: dictionary of namedtuples
    """
    logger.info('Parsing "wp_term_taxonomy.csv" file')
    filename = os.path.join(source, 'wp_term_taxonomy.csv')
    assert os.path.isfile(filename), 'Missing wp_term_taxonomy.csv file'

    TermTaxonomy = namedtuple('TermTaxonomy', ['id', 'taxonomy'])
    mapping = dict()
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel-tab')
        for row in reader:
            mapping[row['term_taxonomy_id']] = TermTaxonomy(
                row['term_id'], row['taxonomy'])

    return mapping


def read_terms(source):
    """Extract terms from a CVS file.

    :param source: [required] path to wp_terms.csv file
    :type obj: string
    :returns:  the term name and slug of each term id
    :rtype: dictionary of tuples
    """
    logger.info('Parsing "wp_terms.csv" file')
    filename = os.path.join(source, 'wp_terms.csv')
    assert os.path.isfile(filename), 'Missing wp_terms.csv file'

    mapping = dict()
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel-tab')
        for row in reader:
            mapping[row['term_id']] = (row['name'], row['slug'])

    return mapping


def get_taxonomies(source):
    """Return the taxonomies associated with each object id. As
    relationships are splited among various files we need to map the
    information for each object.

    In WordPress each object can have only one category and many tags
    associated with it, and the category is used for contructing the
    permalink structure; here we will use it to create containers of
    objects.

    :param source: [required] path to CVS files
    :type obj: string
    :returns:  the category and tags of each object
    :rtype: dictionary of namedtuples
    """
    logger.info('Procesing taxonomies')
    term_relationships = read_term_relationships(source)
    term_taxonomy = read_term_taxonomy(source)
    terms = read_terms(source)
    Taxonomy = namedtuple('Taxonomy', ['category', 'tags'])
    taxonomies = dict()
    # get the list of relations on every object
    for obj, relations in term_relationships.items():
        tags = list()
        for r in relations:
            # translate the term_taxonomy_id into a term_id
            # and get its name and slug
            name, slug = terms[term_taxonomy[r].id]
            # get the taxonomy also
            taxonomy = term_taxonomy[r].taxonomy
            # we take care only of tags and categories
            if taxonomy == 'post_tag':
                tags.append(name)
            elif taxonomy == 'category':
                category = slug
        taxonomies[obj] = Taxonomy(category, tags)

    return taxonomies
