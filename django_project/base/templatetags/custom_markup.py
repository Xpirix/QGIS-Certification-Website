import re

import markdown
from django import template
from django.contrib.staticfiles import finders
from django.template.defaultfilters import stringfilter
from django.utils.encoding import force_str as force_unicode
from django.utils.html import escape
from django.utils.safestring import mark_safe
from core.settings.utils import absolute_path

register = template.Library()

# Schemes permitted in generated links and images. Markdown link syntax
# carries the target through verbatim, so escaping the input is not on its
# own enough to stop `[click](javascript:alert(1))`.
ALLOWED_URL_SCHEMES = frozenset({'http', 'https', 'mailto', 'ftp'})

# Applied to Markdown's own output, where the only attributes present are the
# ones it generates. Matching HTML with a regular expression is normally a
# mistake; it is sound here only because base_markdown() escapes the input
# first, so no user-supplied markup survives into this string.
URL_ATTRIBUTE_RE = re.compile(r'\b(href|src)="([^"]*)"')

SCHEME_RE = re.compile(r'^\s*([a-zA-Z][a-zA-Z0-9+.\-]*):')


@register.filter("klass")
def klass(ob):
    return ob.__class__.__name__


def is_safe_url(url: str) -> bool:
    """Check whether a generated link target is safe to render.

    :param url: The URL taken from a generated href or src attribute.
    :type url: str

    :returns: True for relative URLs and for the allowed schemes.
    :rtype: bool
    """

    scheme = SCHEME_RE.match(url)
    if scheme is None:
        # Relative, anchor, or protocol-relative: no scheme to abuse.
        return True
    return scheme.group(1).lower() in ALLOWED_URL_SCHEMES


def strip_unsafe_urls(html_output: str) -> str:
    """Blank out link and image targets using a disallowed scheme.

    :param html_output: HTML produced by Markdown from escaped input.
    :type html_output: str

    :returns: The same HTML with unsafe targets replaced by an empty value.
    :rtype: str
    """

    def replace(match: re.Match) -> str:
        attribute, url = match.group(1), match.group(2)
        if is_safe_url(url):
            return match.group(0)
        return '%s=""' % attribute

    return URL_ATTRIBUTE_RE.sub(replace, html_output)


@register.filter(name='base_markdown', is_safe=True)
@stringfilter
def base_markdown(value):
    """Render Markdown to HTML without letting the author inject markup.

    The input is escaped before rendering. This filter previously passed
    ``safe_mode=True``, which Python-Markdown removed in 3.0 and now silently
    ignores, so the unsanitised result was handed to mark_safe() and any HTML
    in the source - a checklist answer written by an applicant, for instance -
    executed in the reviewer's session. Escaping first costs nothing, because
    Markdown syntax does not depend on raw HTML being allowed through.

    :param value: The Markdown source.
    :type value: str

    :returns: Rendered, escaped HTML marked safe for the template.
    :rtype: str
    """

    extensions = ["nl2br", "markdown.extensions.tables", "fenced_code"]
    html_output = markdown.markdown(
        escape(force_unicode(value)),
        extensions=extensions,
        enable_attributes=False)
    html_output = html_output.replace(
        '<table>', '<table class="table table-striped table-bordered">')
    return mark_safe(strip_unsafe_urls(html_output))


@register.filter(name='is_gif', is_safe=True)
@stringfilter
def is_gif(value):
    return value[-4:] == '.gif'


@register.filter
def local_static_filepath(value):
    """It gives the local filepath of a static file.

    Inspired by:
    https://stackoverflow.com/questions/9391167/django-how-to-get-a-static-
    files-filepath-in-a-development-environment

    :param value: The name of the static file to look for.

    :return: The local file path.
    """
    return finders.find(value)


@register.filter
def to_char(value):
    """Return a letter according to the number given.

    Eg 1 is returning "a".
    """
    return chr(96 + value)


@register.inclusion_tag('button_span.html', takes_context=True)
def show_button_icon(context, value):

    context_icon = {
        'add': 'glyphicon glyphicon-asterisk',
        'update': 'glyphicon glyphicon-pencil',
        'delete': 'glyphicon glyphicon-minus',
        'back': 'glyphicon glyphicon-arrow-left'
    }

    return {
        'button_icon': context_icon[value]
    }


@register.filter
def columns(thelist, n):
    """
    Break a list into ``n`` columns, filling up each column to the maximum
    equal length possible. For example::
    """
    try:
        n = int(n)
        thelist = list(thelist)
    except (ValueError, TypeError):
        return [thelist]
    list_len = len(thelist)
    split = list_len // n
    if list_len % n != 0:
        split += 1
    return [thelist[i::split] for i in range(split)]


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.simple_tag(takes_context=True)
def version_tag(context):
    """Reads current project release from the .version file."""
    version_file = absolute_path('.version')
    try:
        with open(version_file, 'r') as file:
            version = file.read()
            context['version'] = version
    except IOError:
        context['version'] = 'Unknown'
    return context['version']
