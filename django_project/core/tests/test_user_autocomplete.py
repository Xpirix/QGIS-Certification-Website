# coding=utf-8
"""Tests for the user autocomplete endpoints and selected-only pickers.

These guard against the privacy leak where any logged-in user could scrape
every user's email address or enumerate the whole user directory.
"""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from core.model_factories import UserF


# The test client uses the 'testserver' host; CheckDomainMiddleware only lets
# hosts in VALID_DOMAIN through (and the runner forces DEBUG=False), so allow
# 'testserver' here.
@override_settings(VALID_DOMAIN=['testserver'])
class UserAutocompleteViewTest(TestCase):
    """The autocomplete JSON endpoint must not leak emails or the full list."""

    def setUp(self):
        self.requester = UserF.create(
            username='requester', first_name='', last_name='')
        self.target = UserF.create(
            username='jsmith', first_name='John', last_name='Smith',
            email='john.smith@example.com')
        self.url = reverse('user-autocomplete')

    def test_requires_login(self):
        response = self.client.get(self.url, {'q': 'js'})
        self.assertNotEqual(response.status_code, 200)

    def test_empty_query_returns_empty_list(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.url, {'q': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), [])

    def test_email_never_exposed(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.url, {'q': 'jsmith'})
        self.assertNotIn('john.smith@example.com', response.content.decode())

    def test_display_uses_full_name_and_username(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.url, {'q': 'jsmith'})
        results = json.loads(response.content)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['display'], 'John Smith (jsmith)')
        self.assertEqual(results[0]['value'], self.target.pk)

    def test_display_falls_back_to_username_when_no_name(self):
        UserF.create(username='nameless', first_name='', last_name='')
        self.client.force_login(self.requester)
        response = self.client.get(self.url, {'q': 'nameless'})
        results = json.loads(response.content)
        self.assertEqual(results[0]['display'], 'nameless')

    def test_only_exact_username_matches(self):
        self.client.force_login(self.requester)
        # Substrings and names must not match (no enumeration)...
        for query in ['jsmit', 'smith', 'John', 'Smith']:
            results = json.loads(self.client.get(self.url, {'q': query}).content)
            self.assertEqual(results, [], msg='%r should not match' % query)
        # ...only the exact username does.
        results = json.loads(self.client.get(self.url, {'q': 'jsmith'}).content)
        self.assertEqual([r['value'] for r in results], [self.target.pk])

    def test_username_match_is_case_insensitive(self):
        self.client.force_login(self.requester)
        results = json.loads(self.client.get(self.url, {'q': 'JSmith'}).content)
        self.assertEqual([r['value'] for r in results], [self.target.pk])


@override_settings(VALID_DOMAIN=['testserver'])
class GetUserByPkViewTest(TestCase):
    """Fetching a single user by pk must not leak their email either."""

    def setUp(self):
        self.requester = UserF.create(username='requester')
        self.target = UserF.create(
            username='jsmith', first_name='John', last_name='Smith',
            email='john.smith@example.com')
        self.url = reverse('get-user-by-pk', args=[self.target.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_email_never_exposed(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertNotIn('john.smith@example.com', body)
        self.assertEqual(
            json.loads(body),
            {'value': self.target.pk, 'display': 'John Smith (jsmith)'})
