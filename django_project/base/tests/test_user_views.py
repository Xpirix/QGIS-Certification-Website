# coding=utf-8
"""Authorisation on the user profile update view.

UserUpdateView selected from User.objects.all() and checked ownership in
get_context_data(). Django calls get_context_data() when it renders the form
and when validation fails, but a successful POST goes straight from
get_object() to form_valid() to a redirect - so the check guarded the page
and not the update. Any logged-in user could rewrite any other user's email
address and then take the account over through a password reset.
"""

import logging

from core.model_factories import UserF
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


@override_settings(VALID_DOMAIN=['testserver', ])
class UserUpdateViewTest(TestCase):
    """A victim, an attacker, and the profile page that sat between them."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.victim = self.make_user('victim', email='victim@example.com')
        self.attacker = self.make_user('attacker', email='attacker@evil.test')

    def make_user(self, username: str, **kwargs: object) -> User:
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def update_url(self, user: User) -> str:
        return reverse('edit-profile', kwargs={'pk': user.pk})

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(self.update_url(self.victim))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_user_can_open_their_own_profile(self) -> None:
        self.login('victim')
        response = self.client.get(self.update_url(self.victim))
        self.assertEqual(response.status_code, 200)

    def test_user_can_update_their_own_profile(self) -> None:
        self.login('victim')
        response = self.client.post(self.update_url(self.victim), data={
            'username': 'victim',
            'first_name': 'New',
            'last_name': 'Name',
            'email': 'victim@example.com',
        })
        self.assertEqual(response.status_code, 302)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.first_name, 'New')

    def test_opening_another_users_profile_is_refused(self) -> None:
        self.login('attacker')
        response = self.client.get(self.update_url(self.victim))
        self.assertEqual(response.status_code, 404)

    def test_posting_to_another_users_profile_does_not_change_it(self) -> None:
        """The regression this view existed to allow.

        A POST used to bypass the ownership check entirely, so this asserts
        on the stored email rather than only on the status code.
        """

        self.login('attacker')
        response = self.client.post(self.update_url(self.victim), data={
            'username': 'victim',
            'first_name': 'Pwned',
            'last_name': 'Pwned',
            'email': 'attacker@evil.test',
        })

        self.assertEqual(response.status_code, 404)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.email, 'victim@example.com')
        self.assertNotEqual(self.victim.first_name, 'Pwned')

    def test_staff_cannot_edit_another_user_through_this_view(self) -> None:
        """Staff manage users through the admin, not through this form."""

        staff = self.make_user('staff', is_staff=True)
        self.login('staff')
        response = self.client.post(self.update_url(self.victim), data={
            'username': 'victim',
            'first_name': 'Edited',
            'last_name': 'Edited',
            'email': 'staff@example.com',
        })

        self.assertEqual(response.status_code, 404)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.email, 'victim@example.com')
        self.assertTrue(staff.is_staff)
