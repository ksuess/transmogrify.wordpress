# -*- coding: utf-8 -*-
"""
This module contains the tool of transmogrify.wordpress
"""
from setuptools import find_packages
from setuptools import setup

version = '1.0a1'
description = 'Transmogrifier pipelines for importing a Wordpress blog into Plone.'
long_description = (
    open('README.rst').read() + '\n' +
    open('CONTRIBUTORS.rst').read() + '\n' +
    open('CHANGES.rst').read()
)

setup(name='transmogrify.wordpress',
      version=version,
      description=description,
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
                        'phpserialize',
                        'requests',
                        ],
      extras_require={
          'test': [
              'plone.app.testing',
              'plone.testing',
          ],
      },
      entry_points="""
      # -*- entry_points -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
