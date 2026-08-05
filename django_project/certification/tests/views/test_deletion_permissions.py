# coding=utf-8
"""Authorisation on the training centre, convener and course attendee views.

These three carried only LoginRequiredMixin, so any logged-in user could act
on any organisation's records. Deleting a training centre or a convener
cascades to their courses and every certificate issued for them.
"""

import logging

from certification.models import (
    CertifyingOrganisation,
    CourseAttendee,
    CourseConvener,
    TrainingCenter,
)
from certification.tests.model_factories import (
    AttendeeF,
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
class DeletionPermissionTestBase(TestCase):
    """One organisation, its dependants, and a cast of users."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project)
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

    def training_center_delete_url(self) -> str:
        return reverse('trainingcenter-delete', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'slug': self.training_center.slug,
        })

    def convener_delete_url(self) -> str:
        return reverse('courseconvener-delete', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'slug': self.course_convener.slug,
        })

    def course_attendee_delete_url(self) -> str:
        return reverse('courseattendee-delete', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'course_slug': self.course.slug,
            'pk': self.course_attendee.pk,
        })


class TestTrainingCenterPermissions(DeletionPermissionTestBase):
    """Deleting a training centre cascades to its courses and certificates."""

    def test_outsider_cannot_post_delete(self) -> None:
        self.login('outsider')
        response = self.client.post(self.training_center_delete_url())

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            TrainingCenter.objects.filter(
                pk=self.training_center.pk).exists())

    def test_outsider_cannot_get_delete(self) -> None:
        self.login('outsider')
        response = self.client.get(self.training_center_delete_url())
        self.assertEqual(response.status_code, 403)

    def test_owner_may_open_delete(self) -> None:
        self.login('owner')
        response = self.client.get(self.training_center_delete_url())
        self.assertEqual(response.status_code, 200)

    def test_staff_may_open_delete(self) -> None:
        self.login('staff')
        response = self.client.get(self.training_center_delete_url())
        self.assertEqual(response.status_code, 200)


class TestCourseConvenerPermissions(DeletionPermissionTestBase):
    """Deleting a convener cascades to their courses and certificates."""

    def test_outsider_cannot_post_delete(self) -> None:
        self.login('outsider')
        response = self.client.post(self.convener_delete_url())

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            CourseConvener.objects.filter(
                pk=self.course_convener.pk).exists())

    def test_owner_may_open_delete(self) -> None:
        self.login('owner')
        response = self.client.get(self.convener_delete_url())
        self.assertEqual(response.status_code, 200)


class TestOrganisationDeleteDegradesGracefully(DeletionPermissionTestBase):
    """PROTECT must not surface as an unhandled server error."""

    def test_delete_with_dependants_is_reported_not_a_500(self) -> None:
        self.login('staff')
        response = self.client.post(reverse(
            'certifyingorganisation-delete',
            kwargs={'slug': self.certifying_organisation.slug},
        ))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CertifyingOrganisation.objects.filter(
                pk=self.certifying_organisation.pk).exists())

        # The safety net message is the only explanation the user gets, so it
        # has to reach the page and name what is in the way.
        self.assertContains(response, 'cannot be deleted because other')
        self.assertContains(response, 'training center')
        self.assertContains(response, 'course type')


class TestCourseAttendeePermissions(DeletionPermissionTestBase):
    """This view had no organisation scoping at all."""

    def test_outsider_cannot_post_delete(self) -> None:
        self.login('outsider')
        response = self.client.post(self.course_attendee_delete_url())

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            CourseAttendee.objects.filter(
                pk=self.course_attendee.pk).exists())

    def test_owner_may_delete(self) -> None:
        self.login('owner')
        response = self.client.post(self.course_attendee_delete_url())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CourseAttendee.objects.filter(
                pk=self.course_attendee.pk).exists())

    def test_cannot_reach_another_organisations_course(self) -> None:
        """Pairing your own organisation slug with a foreign course slug.

        The permission check passes for the organisation in the URL, so the
        course lookup has to be scoped to it as well.
        """

        other_organisation = CertifyingOrganisationF.create(
            project=self.project)
        other_organisation.organisation_owners.add(self.owner)
        other_course = CourseF.create(
            certifying_organisation=other_organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=other_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=other_organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=other_organisation),
        )
        victim = self.course_attendee

        self.login('owner')
        response = self.client.post(reverse('courseattendee-delete', kwargs={
            'organisation_slug': other_organisation.slug,
            'course_slug': self.course.slug,
            'pk': victim.pk,
        }))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(CourseAttendee.objects.filter(pk=victim.pk).exists())
        self.assertTrue(other_course.pk is not None)
