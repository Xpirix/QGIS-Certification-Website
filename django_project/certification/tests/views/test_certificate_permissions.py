# coding=utf-8
"""Authorisation on certificate issuing and bulk download.

CertificateCreateView carried LoginRequiredMixin only, and its form_valid()
subtracted the project's certificate_credit from the organisation named in
the URL, so any account could mint genuine, publicly verifiable certificates
against any organisation and spend its credits. The balance itself was
already guarded by CertificateForm.clean(); the missing piece was any check
of who was asking. download_certificates_zip had no check at all, and
returned every paid certificate for a course to anonymous callers.
"""

import logging

from certification.models import Certificate
from certification.tests.model_factories import (
    AttendeeF,
    CertificateTypeF,
    CertifyingOrganisationF,
    CourseAttendeeF,
    CourseConvenerF,
    CourseF,
    CourseTypeF,
    ProjectF,
    TrainingCenterF,
    UserF,
)
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


@override_settings(VALID_DOMAIN=['testserver', ])
class CertificateCreatePermissionTest(TestCase):
    """Issuing a certificate spends money, so it needs a permission check."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create(certificate_credit=1)
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)
        self.course = CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=self.certifying_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=self.certifying_organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=self.certifying_organisation),
        )
        self.attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        CourseAttendeeF.create(course=self.course, attendee=self.attendee)
        self.certificate_type = CertificateTypeF.create()

        self.outsider = self.make_user('outsider')
        self.owner = self.make_user('owner')
        self.certifying_organisation.organisation_owners.add(self.owner)

    def make_user(self, username: str, **kwargs: object):
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def create_url(self) -> str:
        return reverse('certificate-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': self.course.slug,
            'pk': self.attendee.pk,
            'certificate_type_pk': self.certificate_type.pk,
        })

    def credits(self) -> int:
        self.certifying_organisation.refresh_from_db()
        return self.certifying_organisation.organisation_credits

    def valid_post_data(self) -> dict:
        """The form's hidden fields are still required on submission."""

        return {
            'course': self.course.pk,
            'attendee': self.attendee.pk,
            'certificate_type': self.certificate_type.pk,
            'is_paid': True,
        }

    def test_anonymous_cannot_issue_a_certificate(self) -> None:
        response = self.client.post(
            self.create_url(), data=self.valid_post_data())

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        self.assertEqual(Certificate.objects.count(), 0)
        self.assertEqual(self.credits(), 10)

    def test_outsider_cannot_issue_a_certificate(self) -> None:
        """The regression: any account could mint a real certificate."""

        self.login('outsider')
        response = self.client.post(
            self.create_url(), data=self.valid_post_data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Certificate.objects.count(), 0)
        self.assertEqual(self.credits(), 10)

    def test_outsider_cannot_open_the_create_form(self) -> None:
        self.login('outsider')
        response = self.client.get(self.create_url())
        self.assertEqual(response.status_code, 403)

    def test_owner_can_issue_a_certificate(self) -> None:
        self.login('owner')
        response = self.client.post(
            self.create_url(), data=self.valid_post_data())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Certificate.objects.count(), 1)
        self.assertEqual(self.credits(), 9)

    def test_issuing_is_refused_when_credits_would_go_negative(self) -> None:
        """CertificateForm.clean() is what stops this, not the view.

        Pinned here so that the balance rule is not lost if the form is
        rewritten: the form is re-rendered with an error rather than saving.
        """

        self.certifying_organisation.organisation_credits = 0
        self.certifying_organisation.save()

        self.login('owner')
        response = self.client.post(
            self.create_url(), data=self.valid_post_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Insufficient credits')
        self.assertEqual(Certificate.objects.count(), 0)
        self.assertEqual(self.credits(), 0)

    def test_attendee_of_another_organisation_is_not_reachable(self) -> None:
        """Rights over one organisation must not reach another's attendee."""

        other_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)
        other_attendee = AttendeeF.create(
            certifying_organisation=other_organisation)

        self.login('owner')
        response = self.client.post(reverse('certificate-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': self.course.slug,
            'pk': other_attendee.pk,
            'certificate_type_pk': self.certificate_type.pk,
        }), data=self.valid_post_data())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Certificate.objects.count(), 0)


@override_settings(VALID_DOMAIN=['testserver', ])
class DownloadCertificatesZipPermissionTest(TestCase):
    """The bulk download was a public export of the attendee roster."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create(certificate_credit=1)
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)
        self.course = CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=self.certifying_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=self.certifying_organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=self.certifying_organisation),
        )

        self.outsider = self.make_user('outsider')
        self.owner = self.make_user('owner')
        self.certifying_organisation.organisation_owners.add(self.owner)

    def make_user(self, username: str, **kwargs: object):
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def download_url(self) -> str:
        return reverse('download_zip_all', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': self.course.slug,
        })

    def test_anonymous_cannot_download_the_zip(self) -> None:
        """The regression: this needed no credentials at all."""

        response = self.client.get(self.download_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_outsider_cannot_download_the_zip(self) -> None:
        self.login('outsider')
        response = self.client.get(self.download_url())
        self.assertEqual(response.status_code, 403)

    def test_owner_can_download_the_zip(self) -> None:
        self.login('owner')
        response = self.client.get(self.download_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'], 'application/x-zip-compressed')
