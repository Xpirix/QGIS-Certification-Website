# coding=utf-8
"""Authorisation on the certificate paid-status view.

update_paid_status was a plain function view with no authentication and no
permission check at all. Its POST branch marks certificates paid and
subtracts credits - which organisations buy with real money - and its GET
branch rendered the confirmation form, and so a CSRF token, to anyone who
asked. An unauthenticated attacker could therefore drain any organisation's
balance in a loop, and the deduction had no lower bound so the balance went
negative.
"""

import logging

from certification.models import Certificate, CertifyingOrganisation
from certification.tests.model_factories import (
    AttendeeF,
    CertificateF,
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
class UpdatePaidStatusPermissionTest(TestCase):
    """One organisation with credits, and users of varying entitlement."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create(certificate_credit=1)
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)
        self.training_center = TrainingCenterF.create(
            certifying_organisation=self.certifying_organisation)
        self.course_convener = CourseConvenerF.create(
            certifying_organisation=self.certifying_organisation)
        self.course_type = CourseTypeF.create(
            certifying_organisation=self.certifying_organisation)
        self.course = CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=self.training_center,
            course_convener=self.course_convener,
            course_type=self.course_type,
        )
        self.attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        self.course_attendee = CourseAttendeeF.create(
            course=self.course, attendee=self.attendee)
        self.certificate = CertificateF.create(
            course=self.course, attendee=self.attendee, is_paid=False)

        self.outsider = self.make_user('outsider')
        self.staff = self.make_user('staff', is_staff=True)
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

    def paid_status_url(self) -> str:
        return reverse('paid-certificate', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': self.course.slug,
            'pk': self.attendee.pk,
        })

    def credits(self) -> int:
        self.certifying_organisation.refresh_from_db()
        return self.certifying_organisation.organisation_credits

    def test_anonymous_post_does_not_spend_credits(self) -> None:
        """The regression: no login, no check, credits gone."""

        response = self.client.post(self.paid_status_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        self.assertEqual(self.credits(), 10)
        self.certificate.refresh_from_db()
        self.assertFalse(self.certificate.is_paid)

    def test_anonymous_get_does_not_hand_out_the_form(self) -> None:
        """The GET branch used to leak a usable CSRF token."""

        response = self.client.get(self.paid_status_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_outsider_cannot_spend_another_organisations_credits(self) -> None:
        self.login('outsider')
        response = self.client.post(self.paid_status_url())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.credits(), 10)
        self.certificate.refresh_from_db()
        self.assertFalse(self.certificate.is_paid)

    def test_owner_may_mark_paid(self) -> None:
        self.login('owner')
        response = self.client.post(self.paid_status_url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.credits(), 9)
        self.certificate.refresh_from_db()
        self.assertTrue(self.certificate.is_paid)

    def test_staff_may_mark_paid(self) -> None:
        self.login('staff')
        response = self.client.post(self.paid_status_url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.credits(), 9)

    def test_owner_may_open_the_confirmation_page(self) -> None:
        self.login('owner')
        response = self.client.get(self.paid_status_url())
        self.assertEqual(response.status_code, 200)

    def test_credits_cannot_go_negative(self) -> None:
        """The deduction previously had no lower bound."""

        self.certifying_organisation.organisation_credits = 0
        self.certifying_organisation.save()

        self.login('owner')
        response = self.client.post(self.paid_status_url())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.credits(), 0)
        self.certificate.refresh_from_db()
        self.assertFalse(self.certificate.is_paid)

    def test_course_from_another_organisation_is_not_reachable(self) -> None:
        """Pairing your own org slug with someone else's course must fail.

        CourseAttendeeDeleteView.get_course() documents this same trap: a
        permission check that passes for organisation A must not then act on
        organisation B's course.
        """

        other_organisation = CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)
        other_course = CourseF.create(
            certifying_organisation=other_organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=other_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=other_organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=other_organisation),
        )
        other_attendee = AttendeeF.create(
            certifying_organisation=other_organisation)
        other_certificate = CertificateF.create(
            course=other_course, attendee=other_attendee, is_paid=False)

        self.login('owner')
        response = self.client.post(reverse('paid-certificate', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': other_course.slug,
            'pk': other_attendee.pk,
        }))

        self.assertEqual(response.status_code, 404)
        other_certificate.refresh_from_db()
        self.assertFalse(other_certificate.is_paid)
        self.assertEqual(
            CertifyingOrganisation.objects.get(
                pk=other_organisation.pk).organisation_credits, 10)
        self.assertEqual(self.credits(), 10)

    def test_only_the_named_attendees_certificate_is_marked(self) -> None:
        """Marking one attendee paid must not touch the rest of the course."""

        second_attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        CourseAttendeeF.create(
            course=self.course, attendee=second_attendee)
        second_certificate = CertificateF.create(
            course=self.course, attendee=second_attendee, is_paid=False)

        self.login('owner')
        self.client.post(self.paid_status_url())

        second_certificate.refresh_from_db()
        self.assertFalse(second_certificate.is_paid)
        self.assertEqual(
            Certificate.objects.filter(
                course=self.course, is_paid=True).count(), 1)
