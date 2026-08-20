# coding=utf-8
"""Pricing and authorisation on the Stripe checkout session view.

CreateCheckoutSessionView read "unit" and "total" straight from the query
string and used them to build the Stripe session, so the buyer set their own
price: unit=10000&total=1 gave int(100 / 10000) = 0 cents per credit while
the credits_quantity metadata still said 10000. It also never checked that
the requesting user had anything to do with the organisation named in "org",
so credits could be pushed into an unrelated one.

The flow is no longer linked from the top-up page - the JavaScript that built
this URL is inside a {% comment %} block, and Payrexx has replaced it - but
the route is still live, so it is still reachable directly.
"""

import logging
from decimal import Decimal
from unittest import mock

from certification.tests.model_factories import (
    CertifyingOrganisationF,
    ProjectF,
    UserF,
)
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


@override_settings(VALID_DOMAIN=['testserver', ])
class CreateCheckoutSessionViewTest(TestCase):
    """The server, not the client, decides what credits cost."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create(credit_cost=Decimal('5.00'))
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=0)

        self.owner = self.make_user('owner')
        self.certifying_organisation.organisation_owners.add(self.owner)
        self.outsider = self.make_user('outsider')

    def make_user(self, username: str, **kwargs: object):
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def checkout_url(self, **params: object) -> str:
        query = '&'.join('%s=%s' % item for item in params.items())
        return '%s?%s' % (reverse('checkout'), query)

    def test_anonymous_is_redirected_to_login(self) -> None:
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=10, total=1))

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_outsider_cannot_buy_credits_for_another_organisation(
            self) -> None:
        """The regression: "org" was never checked against the buyer."""

        self.login('outsider')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=10, total=50))

        self.assertEqual(response.status_code, 403)

    def test_unknown_organisation_is_not_found(self) -> None:
        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=999999, unit=10, total=50))

        self.assertEqual(response.status_code, 404)

    def test_zero_credits_is_refused(self) -> None:
        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=0, total=50))

        self.assertEqual(response.status_code, 404)

    def test_negative_credits_is_refused(self) -> None:
        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=-5, total=50))

        self.assertEqual(response.status_code, 404)

    def test_non_numeric_credits_is_refused(self) -> None:
        """This used to raise ValueError and return a 500."""

        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit='abc', total=50))

        self.assertEqual(response.status_code, 404)

    def test_absurd_quantity_is_refused(self) -> None:
        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=10000000, total=1))

        self.assertEqual(response.status_code, 404)

    @mock.patch('certification.views.certificate.PaymentIntent.objects.create')
    @mock.patch('certification.views.certificate.stripe.checkout.Session'
                '.create')
    def test_price_comes_from_the_project_not_the_query_string(
            self, session_create, payment_intent_create) -> None:
        """The heart of it: "total" is ignored entirely.

        credit_cost is 5.00, so 10 credits must be charged at 500 cents each
        however small a "total" the client asks for.
        """

        session_create.return_value = mock.Mock(id='cs_test_123')

        self.login('owner')
        response = self.client.get(self.checkout_url(
            org=self.certifying_organisation.pk, unit=10, total=1))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(session_create.called)

        line_item = session_create.call_args.kwargs['line_items'][0]
        self.assertEqual(line_item['price_data']['unit_amount'], 500)
        self.assertEqual(line_item['quantity'], 10)

        metadata = session_create.call_args.kwargs['metadata']
        self.assertEqual(metadata['credits_quantity'], 10)

        # The PaymentIntent must record the real total, not the client's.
        self.assertEqual(
            payment_intent_create.call_args.kwargs['amount'], 5000)
