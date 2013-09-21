# -*- coding: utf-8 -*-
"""
This module contains the tool of transmogrify.wordpress
"""
import os
from setuptools import setup, find_packages


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '1.0a1'

long_description = (
    read('README.rst')
    + '\n' +
    read('CHANGES.txt')
    + '\n' +
    'Download\n'
    '********\n')

tests_require = ['zope.testing']

setup(name='transmogrify.wordpress',
      version=version,
      description="collective.transmogrifier pipeline to import a blog from Wordpress to Plone",
      long_description=long_description,
      classifiers=[
        'Framework :: Plone',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        ],
      keywords='import wordpress blog plone transmogrifier pipeline blueprint wxr',
      author='David Glick, Groundwire',
      author_email='davidglick@groundwire.org',
      url='http://svn.plone.org/svn/collective/transmogrify.wordpress/trunk',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['transmogrify', ],
      include_package_data=True,
      zip_safe=False,
      install_requires=['setuptools',
                        'collective.transmogrifier',
                        'plone.app.transmogrifier',
                        'lxml',
                        'phpserialize'
                        # -*- Extra requirements: -*-
                        ],
      tests_require=tests_require,
      extras_require=dict(tests=tests_require),
      test_suite='transmogrify.wordpress.tests.test_docs.test_suite',
      entry_points="""
      # -*- entry_points -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
