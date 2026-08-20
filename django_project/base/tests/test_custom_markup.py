# coding=utf-8
"""Escaping in the base_markdown template filter.

The filter passed safe_mode=True to markdown.markdown(). Python-Markdown
removed safe_mode in 3.0 and ignores unknown keyword arguments without
complaining, so nothing was sanitised and the result was handed to
mark_safe(). Checklist answers are free text submitted by anyone applying for
a certifying organisation, and they are rendered through this filter on the
page a reviewer opens - so the payload ran in the reviewer's session.
"""

from base.templatetags.custom_markup import base_markdown
from django.test import TestCase


class BaseMarkdownTest(TestCase):
    """The filter must render Markdown but never the author's own HTML."""

    def test_script_tag_is_escaped(self) -> None:
        """The regression: this used to reach the page intact."""

        output = base_markdown('<script>alert(1)</script>hi')

        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)

    def test_event_handler_attribute_is_escaped(self) -> None:
        """The payload may survive as text, but not as a tag.

        Asserting on the absence of the string "onerror" would be wrong: it
        is inert once the angle brackets are entities, and the reviewer is
        entitled to read what the applicant actually typed.
        """

        output = base_markdown('<img src=x onerror=alert(1)>')

        self.assertNotIn('<img', output)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', output)

    def test_javascript_url_is_removed(self) -> None:
        """Escaping alone does not help here.

        Markdown link syntax carries the target through verbatim, so the
        scheme has to be checked separately.
        """

        output = base_markdown('[click](javascript:alert(1))')

        self.assertNotIn('javascript:', output)
        self.assertIn('href=""', output)

    def test_javascript_url_is_removed_whatever_the_casing(self) -> None:
        output = base_markdown('[click](JaVaScRiPt:alert(1))')
        self.assertNotIn('alert(1)', output)

    def test_vbscript_url_is_removed(self) -> None:
        output = base_markdown('[x](vbscript:msgbox(1))')
        self.assertNotIn('vbscript:', output)

    def test_data_url_is_removed(self) -> None:
        output = base_markdown('[x](data:text/html,hello)')
        self.assertNotIn('data:text/html', output)

    def test_http_links_still_work(self) -> None:
        output = base_markdown('[QGIS](https://qgis.org)')

        self.assertIn('href="https://qgis.org"', output)
        self.assertIn('QGIS', output)

    def test_relative_links_still_work(self) -> None:
        output = base_markdown('[profile](/en/profile/)')
        self.assertIn('href="/en/profile/"', output)

    def test_mailto_links_still_work(self) -> None:
        output = base_markdown('[mail](mailto:someone@example.com)')
        self.assertIn('mailto:someone@example.com', output)

    def test_emphasis_and_code_still_render(self) -> None:
        output = base_markdown('**bold** and *em* and `code`')

        self.assertIn('<strong>bold</strong>', output)
        self.assertIn('<em>em</em>', output)
        self.assertIn('<code>code</code>', output)

    def test_tables_still_render_with_their_classes(self) -> None:
        output = base_markdown('| a | b |\n|---|---|\n| 1 | 2 |')

        self.assertIn(
            '<table class="table table-striped table-bordered">', output)
        self.assertIn('<th>a</th>', output)

    def test_ampersand_is_not_double_escaped(self) -> None:
        """Escaping twice would show the user a literal &amp;amp;."""

        output = base_markdown('Tom & Jerry')

        self.assertIn('Tom &amp; Jerry', output)
        self.assertNotIn('&amp;amp;', output)

    def test_newlines_still_become_breaks(self) -> None:
        """The nl2br extension is what the checklist answers rely on."""

        output = base_markdown('line1\nline2')
        self.assertIn('<br', output)
