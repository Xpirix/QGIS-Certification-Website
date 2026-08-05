# coding=utf-8
"""Tests for revoking a certificate: the 7 day window and the credit refund."""

import datetime
import logging

from certification.models import Certificate, CertifyingOrganisation
from certification.tests.model_factories import (
    AttendeeF,
    CertificateF,
    CertificateTypeF,
    CertifyingOrganisationF,
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
class CertificateRevokeTestBase(TestCase):
    """One organisation with a paid certificate ready to revoke."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create()
        self.project.certificate_credit = 5
        self.project.save()

        self.organisation = CertifyingOrganisationF.create(
            project=self.project)
        self.organisation.organisation_credits = 10
        self.organisation.save()

        self.user = UserF.create(username='staff', is_staff=True)
        self.user.set_password('password')
        self.user.save()

        self.course = CourseF.create(
            certifying_organisation=self.organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=self.organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=self.organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=self.organisation),
        )
        self.attendee = AttendeeF.create(
            certifying_organisation=self.organisation)
        self.certificate = CertificateF.create(
            course=self.course,
            attendee=self.attendee,
            certificate_type=CertificateTypeF.create(),
        )

    def set_issue_date(self, days_ago: int) -> None:
        """Move the certificate issue date, which opens or closes the window.

        issue_date is auto_now_add, so it has to be written with an update()
        rather than through save().
        """

        Certificate.objects.filter(pk=self.certificate.pk).update(
            issue_date=datetime.date.today() - datetime.timedelta(
                days=days_ago))
        self.certificate.refresh_from_db()

    def clear_issue_date(self) -> None:
        """Legacy certificates have no issue date at all."""

        Certificate.objects.filter(pk=self.certificate.pk).update(
            issue_date=None)
        self.certificate.refresh_from_db()

    def revoke_url(self) -> str:
        return reverse('revoke-certificate', kwargs={
            'organisation_slug': self.organisation.slug,
            'course_slug': self.course.slug,
            'pk': self.attendee.pk,
        })

    def organisation_credits(self) -> int:
        return CertifyingOrganisation.objects.get(
            pk=self.organisation.pk).organisation_credits


class TestRevokeWindow(CertificateRevokeTestBase):
    """The window is enforced on POST, not only on GET."""

    def test_revoke_allowed_inside_window(self) -> None:
        self.set_issue_date(days_ago=1)
        self.client.login(username='staff', password='password')

        response = self.client.post(self.revoke_url())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Certificate.objects.filter(pk=self.certificate.pk).exists())

    def test_post_is_refused_outside_window(self) -> None:
        """Enforcing on GET alone left the window bypassable by POSTing."""

        self.set_issue_date(days_ago=90)
        self.client.login(username='staff', password='password')

        response = self.client.post(self.revoke_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Certificate.objects.filter(pk=self.certificate.pk).exists())

    def test_get_is_refused_outside_window(self) -> None:
        self.set_issue_date(days_ago=90)
        self.client.login(username='staff', password='password')

        response = self.client.get(self.revoke_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Certificate.objects.filter(pk=self.certificate.pk).exists())

    def test_refusal_redirects_to_the_course(self) -> None:
        """A readable page, rather than the bare 403 text it used to return."""

        self.set_issue_date(days_ago=90)
        self.client.login(username='staff', password='password')

        response = self.client.get(self.revoke_url())

        self.assertRedirects(response, reverse('course-detail', kwargs={
            'organisation_slug': self.organisation.slug,
            'slug': self.course.slug,
        }))


    def test_certificate_without_issue_date_is_permanent(self) -> None:
        """Legacy rows predating issue_date are kept, not revocable."""

        self.clear_issue_date()
        self.client.login(username='staff', password='password')

        response = self.client.post(self.revoke_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Certificate.objects.filter(pk=self.certificate.pk).exists())

    def test_moving_the_course_end_date_does_not_reopen_the_window(self) -> None:
        """end_date is user-editable, so it must not govern revocation.

        Keying the window to the course end date would let anyone who can
        edit a course reopen revocation indefinitely.
        """

        self.set_issue_date(days_ago=90)
        self.course.end_date = datetime.date.today()
        self.course.save()

        self.client.login(username='staff', password='password')
        response = self.client.post(self.revoke_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Certificate.objects.filter(pk=self.certificate.pk).exists())


class TestRevokeRefundsCredit(CertificateRevokeTestBase):
    """The refund lived in delete(), which Django 4 never calls."""

    def test_revoking_refunds_the_certificate_credit(self) -> None:
        self.set_issue_date(days_ago=1)
        credits_before = self.organisation_credits()

        self.client.login(username='staff', password='password')
        self.client.post(self.revoke_url())

        self.assertEqual(
            self.organisation_credits(),
            credits_before + self.project.certificate_credit,
        )

    def test_refused_revocation_does_not_refund(self) -> None:
        self.set_issue_date(days_ago=90)
        credits_before = self.organisation_credits()

        self.client.login(username='staff', password='password')
        self.client.post(self.revoke_url())

        self.assertEqual(self.organisation_credits(), credits_before)
