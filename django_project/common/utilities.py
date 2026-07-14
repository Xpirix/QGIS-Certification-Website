# coding=utf-8
"""**Utilities functions**
"""

__author__ = 'Ismail Sunni <ismail@kartoza.com>'
__revision__ = '$Format:%H$'
__date__ = '23/04/2014'
__license__ = ''
__copyright__ = ''


from slugify import Slugify

version_slugify = Slugify()
version_slugify.safe_chars = '.'


def format_user_display(user):
    """Human-readable label for a user that never exposes their email."""
    full_name = user.get_full_name()
    return f"{full_name} ({user.username})" if full_name else user.username
