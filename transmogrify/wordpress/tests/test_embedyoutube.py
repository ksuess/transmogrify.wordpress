# -*- coding: utf-8 -*-
from transmogrify.wordpress.blueprints.embedyoutube import YOUTUBE_RE

import unittest


class EmbedYoutubeTestCase(unittest.TestCase):

    def test_regex(self):
        html = """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="UTF-8">
            <title></title>
          </head>
          <body>
            [youtube id="NwTxjNhGpOM"]
          </body>
        </html>
        """
        self.assertIn('iframe', YOUTUBE_RE.sub('iframe', html))

        html = """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="UTF-8">
            <title></title>
          </head>
          <body>
            [youtube id=\"NwTxjNhGpOM\"]
          </body>
        </html>
        """
        self.assertIn('iframe', YOUTUBE_RE.sub('iframe', html))

        html = """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="UTF-8">
            <title></title>
          </head>
          <body>
            [youtube id=\NwTxjNhGpOM"]
          </body>
        </html>
        """
        self.assertIn('iframe', YOUTUBE_RE.sub('iframe', html))

        html = """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="UTF-8">
            <title></title>
          </head>
          <body>
          </body>
        </html>
        """
        self.assertNotIn('iframe', YOUTUBE_RE.sub('iframe', html))
