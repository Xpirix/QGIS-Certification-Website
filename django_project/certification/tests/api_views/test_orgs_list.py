# coding=utf-8
import logging

from certification.tests.model_factories import CertifyingOrganisationF, ProjectF, UserF
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


class TestCertifyingOrganisationView(TestCase):
    """Test that Certifying Organisation View works."""

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def setUp(self):
        """
        Setup before each test
        We force the locale to en otherwise it will use
        the locale of the host running the tests and we
        will get unpredictable results / 404s
        """

        self.client = Client()
        self.client.post("/set_language/", data={"language": "en"})
        logging.disable(logging.CRITICAL)
        self.user = UserF.create(
            **{"username": "anita", "password": "password", "is_staff": True}
        )
        self.user.set_password("password")
        self.user.save()
        self.simple_user = UserF.create(
            **{"username": "user", "password": "password", "is_staff": False}
        )

        self.simple_user.set_password("password")
        self.simple_user.save()
        self.project = ProjectF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project
        )
        self.pending_certifying_organisation = CertifyingOrganisationF.create(
            name="test organisation rejected",
            project=self.project,
            approved=False,
        )

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def tearDown(self):
        """
        Teardown after each test.

        :return:
        """

        # Redundant under TestCase's transaction rollback, and impossible now
        # that the relations are PROTECTed: it deleted parents before children.
        pass

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_get_certifying_organisation_list_api_view(self):
        """
        Test that the certifying organisation list API view returns a list of certifying organisations.
        """
        url = reverse("feed-certifyingorganisations")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())
        self.assertGreater(len(response.json()["results"]), 0)
