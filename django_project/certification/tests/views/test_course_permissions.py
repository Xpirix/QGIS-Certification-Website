# coding=utf-8
"""Tests for the server-side permission checks and the delete guards that
protect courses and course types from cascading deletions."""

import logging
from datetime import date, timedelta

from certification.models import Certificate, Course, CourseType
from certification.tests.model_factories import (
    AttendeeF,
    CertificateF,
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
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


@override_settings(VALID_DOMAIN=['testserver', ])
class CoursePermissionTestBase(TestCase):
    """Shared fixtures: one organisation, one course and a cast of users."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project
        )
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

        self.outsider = self.make_user('outsider')
        self.staff = self.make_user('staff', is_staff=True)
        self.owner = self.make_user('owner')
        self.certifying_organisation.organisation_owners.add(self.owner)

        # The convener is a user in their own right and may edit their course.
        self.convener_user = self.course_convener.user
        self.convener_user.set_password('password')
        self.convener_user.save()

    def make_user(self, username: str, **kwargs: object) -> User:
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def course_delete_url(self) -> str:
        return reverse('course-delete', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'slug': self.course.slug,
        })

    def course_update_url(self) -> str:
        return reverse('course-update', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'slug': self.course.slug,
        })

    def coursetype_delete_url(self) -> str:
        return reverse('coursetype-delete', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'pk': self.course_type.pk,
        })

    def coursetype_update_url(self) -> str:
        return reverse('coursetype-update', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
            'pk': self.course_type.pk,
        })


class TestCoursePermissions(CoursePermissionTestBase):
    """Only staff, organisation owners and the convener may modify a course."""

    def test_outsider_cannot_get_course_delete(self) -> None:
        self.login('outsider')
        response = self.client.get(self.course_delete_url())
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_post_course_delete(self) -> None:
        """POSTing directly is the hole a hidden button does not close."""

        self.login('outsider')
        response = self.client.post(self.course_delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_outsider_cannot_post_course_update(self) -> None:
        self.login('outsider')
        response = self.client.post(self.course_update_url(), data={})
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_post_coursetype_update(self) -> None:
        """CourseTypeUpdateView used to expose CourseType.objects.all()."""

        self.login('outsider')
        response = self.client.post(self.coursetype_update_url(), data={})
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_post_coursetype_delete(self) -> None:
        self.login('outsider')
        response = self.client.post(self.coursetype_delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            CourseType.objects.filter(pk=self.course_type.pk).exists())

    def test_staff_may_open_course_delete(self) -> None:
        self.login('staff')
        response = self.client.get(self.course_delete_url())
        self.assertEqual(response.status_code, 200)

    def test_organisation_owner_may_open_course_delete(self) -> None:
        self.login('owner')
        response = self.client.get(self.course_delete_url())
        self.assertEqual(response.status_code, 200)

    def test_convener_may_open_course_delete(self) -> None:
        self.login(self.convener_user.username)
        response = self.client.get(self.course_delete_url())
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_open_course_create(self) -> None:
        self.login('outsider')
        response = self.client.get(reverse('course-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
        }))
        self.assertEqual(response.status_code, 403)

    def test_convener_may_open_course_create(self) -> None:
        """The organisation detail page offers conveners this button."""

        self.login(self.convener_user.username)
        response = self.client.get(reverse('course-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
        }))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_open_coursetype_create(self) -> None:
        self.login('outsider')
        response = self.client.get(reverse('coursetype-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
        }))
        self.assertEqual(response.status_code, 403)

    def test_owner_may_open_coursetype_create(self) -> None:
        self.login('owner')
        response = self.client.get(reverse('coursetype-create', kwargs={
            'organisation_slug': self.certifying_organisation.slug,
        }))
        self.assertEqual(response.status_code, 200)

    def test_convener_may_not_delete_another_organisations_course(self) -> None:
        """The convener exception is scoped to their own course."""

        other_organisation = CertifyingOrganisationF.create(
            project=self.project)
        # Every related object is passed explicitly: the sub-factories would
        # otherwise build a second Project, whose name is unique.
        other_course = CourseF.create(
            certifying_organisation=other_organisation,
            course_type=CourseTypeF.create(
                certifying_organisation=other_organisation),
            training_center=TrainingCenterF.create(
                certifying_organisation=other_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=other_organisation),
        )
        self.login(self.convener_user.username)
        response = self.client.post(reverse('course-delete', kwargs={
            'organisation_slug': other_organisation.slug,
            'slug': other_course.slug,
        }))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Course.objects.filter(pk=other_course.pk).exists())


class TestCourseTypeDeleteGuard(CoursePermissionTestBase):
    """A course type with courses must not be deletable."""

    def test_delete_blocked_while_course_exists(self) -> None:
        self.login('staff')
        response = self.client.post(self.coursetype_delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CourseType.objects.filter(pk=self.course_type.pk).exists())
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())
        self.assertContains(response, 'cannot be deleted yet')

    def test_deleting_course_type_never_removes_certificates(self) -> None:
        """The regression this whole change exists to prevent."""

        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        CertificateF.create(
            course=self.course,
            attendee=attendee,
            certificate_type=CertificateTypeF.create(),
        )
        certificates_before = Certificate.objects.count()

        self.login('staff')
        self.client.post(self.coursetype_delete_url())

        self.assertEqual(Certificate.objects.count(), certificates_before)

    def issue_certificate_on_course(self, issued_days_ago: int) -> None:
        """Attach a back-dated certificate to this course type's course."""

        certificate = CertificateF.create(
            course=self.course,
            attendee=AttendeeF.create(
                certifying_organisation=self.certifying_organisation),
            certificate_type=CertificateTypeF.create(),
        )
        Certificate.objects.filter(pk=certificate.pk).update(
            issue_date=date.today() - timedelta(days=issued_days_ago))

    def test_message_says_never_when_a_course_is_permanent(self) -> None:
        """Surfaced here so the user does not walk each course to find out."""

        self.issue_certificate_on_course(issued_days_ago=90)

        self.login('staff')
        response = self.client.get(self.coursetype_delete_url())

        self.assertContains(response, 'This course type cannot be deleted.')
        self.assertContains(response, 'can no longer be revoked')
        self.assertNotContains(response, 'cannot be deleted yet')

    def test_message_says_not_yet_when_courses_are_still_removable(
            self) -> None:
        self.issue_certificate_on_course(issued_days_ago=1)

        self.login('staff')
        response = self.client.get(self.coursetype_delete_url())

        self.assertContains(
            response, 'This course type cannot be deleted yet.')
        self.assertContains(response, 'can still be revoked')
        self.assertNotContains(response, 'permanent record')

    def test_message_says_not_yet_when_course_has_no_certificates(
            self) -> None:
        self.login('staff')
        response = self.client.get(self.coursetype_delete_url())

        self.assertContains(
            response, 'This course type cannot be deleted yet.')

    def test_delete_succeeds_once_courses_are_removed(self) -> None:
        """The guard defers deletion, it does not forbid it forever."""

        self.course.delete()

        self.login('staff')
        response = self.client.post(self.coursetype_delete_url())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CourseType.objects.filter(pk=self.course_type.pk).exists())


class TestCourseDeleteGuard(CoursePermissionTestBase):
    """A course holding certificates or attendees must not be deletable."""

    def test_delete_blocked_by_certificate(self) -> None:
        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        CertificateF.create(
            course=self.course,
            attendee=attendee,
            certificate_type=CertificateTypeF.create(),
        )

        self.login('staff')
        response = self.client.post(self.course_delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())
        self.assertEqual(Certificate.objects.count(), 1)
        self.assertContains(response, 'cannot be deleted yet')

    def test_delete_blocked_by_course_attendee(self) -> None:
        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation)
        CourseAttendeeF.create(course=self.course, attendee=attendee)

        self.login('staff')
        response = self.client.post(self.course_delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def issue_certificate(self, issued_days_ago: int) -> Certificate:
        """Attach a certificate with a back-dated issue date.

        issue_date is auto_now_add, so it has to be written with update().
        """

        certificate = CertificateF.create(
            course=self.course,
            attendee=AttendeeF.create(
                certifying_organisation=self.certifying_organisation),
            certificate_type=CertificateTypeF.create(),
        )
        Certificate.objects.filter(pk=certificate.pk).update(
            issue_date=date.today() - timedelta(days=issued_days_ago))
        return certificate

    def test_message_says_never_when_a_certificate_is_permanent(self) -> None:
        """Past the window there is no sequence of steps that frees the course."""

        self.issue_certificate(issued_days_ago=90)

        self.login('staff')
        response = self.client.get(self.course_delete_url())

        self.assertContains(response, 'This course cannot be deleted.')
        self.assertContains(response, 'can no longer be revoked')
        self.assertNotContains(response, 'cannot be deleted yet')

    def test_message_says_not_yet_when_all_certificates_are_revocable(
            self) -> None:
        self.issue_certificate(issued_days_ago=1)

        self.login('staff')
        response = self.client.get(self.course_delete_url())

        self.assertContains(response, 'This course cannot be deleted yet.')
        self.assertContains(response, 'can still be revoked')
        self.assertNotContains(response, 'permanent record')

    def test_one_permanent_certificate_is_enough_to_block_forever(self) -> None:
        """A mix of revocable and permanent still means permanent."""

        self.issue_certificate(issued_days_ago=1)
        self.issue_certificate(issued_days_ago=90)

        self.login('staff')
        response = self.client.get(self.course_delete_url())

        self.assertContains(response, 'This course cannot be deleted.')
        self.assertNotContains(response, 'cannot be deleted yet')

    def test_delete_succeeds_when_course_has_no_children(self) -> None:
        self.login('staff')
        response = self.client.post(self.course_delete_url())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
