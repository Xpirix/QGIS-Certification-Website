# coding=utf-8
"""The on_delete=PROTECT rules that make deletion strictly bottom-up.

Every relation that could reach a Certificate used to cascade. Deleting one
training centre, convener, course type, organisation or user destroyed every
certificate beneath it, with nothing in the interface saying so.
"""

from certification.models import Certificate, CertifyingOrganisation
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
)
from django.db.models import ProtectedError
from django.test import TestCase


class ProtectedRelationTestBase(TestCase):
    """A full chain: project → organisation → course → certificate."""

    def setUp(self) -> None:
        self.project = ProjectF.create()
        self.organisation = CertifyingOrganisationF.create(
            project=self.project)
        self.training_center = TrainingCenterF.create(
            certifying_organisation=self.organisation)
        self.course_convener = CourseConvenerF.create(
            certifying_organisation=self.organisation)
        self.course_type = CourseTypeF.create(
            certifying_organisation=self.organisation)
        self.course = CourseF.create(
            certifying_organisation=self.organisation,
            training_center=self.training_center,
            course_convener=self.course_convener,
            course_type=self.course_type,
        )
        self.attendee = AttendeeF.create(
            certifying_organisation=self.organisation)
        self.course_attendee = CourseAttendeeF.create(
            course=self.course, attendee=self.attendee)
        self.certificate = CertificateF.create(
            course=self.course,
            attendee=self.attendee,
            certificate_type=CertificateTypeF.create(),
        )

    def assertCertificateSurvives(self) -> None:
        self.assertTrue(
            Certificate.objects.filter(pk=self.certificate.pk).exists())


class TestCertificateCannotBeCascadedAway(ProtectedRelationTestBase):
    """No parent may take a certificate with it."""

    def test_training_center_is_protected(self) -> None:
        """The case that prompted this work."""

        with self.assertRaises(ProtectedError):
            self.training_center.delete()
        self.assertCertificateSurvives()

    def test_course_convener_is_protected(self) -> None:
        with self.assertRaises(ProtectedError):
            self.course_convener.delete()
        self.assertCertificateSurvives()

    def test_course_type_is_protected(self) -> None:
        with self.assertRaises(ProtectedError):
            self.course_type.delete()
        self.assertCertificateSurvives()

    def test_certifying_organisation_is_protected(self) -> None:
        with self.assertRaises(ProtectedError):
            self.organisation.delete()
        self.assertCertificateSurvives()

    def test_project_is_protected(self) -> None:
        """Deleting the project reached every certificate in the system."""

        with self.assertRaises(ProtectedError):
            self.project.delete()
        self.assertCertificateSurvives()
        self.assertTrue(
            CertifyingOrganisation.objects.filter(
                pk=self.organisation.pk).exists())

    def test_course_is_protected(self) -> None:
        with self.assertRaises(ProtectedError):
            self.course.delete()
        self.assertCertificateSurvives()

    def test_attendee_is_protected(self) -> None:
        with self.assertRaises(ProtectedError):
            self.attendee.delete()
        self.assertCertificateSurvives()

    def test_author_user_is_protected(self) -> None:
        """One user's deletion could destroy 1,714 certificates."""

        with self.assertRaises(ProtectedError):
            self.certificate.author.delete()
        self.assertCertificateSurvives()


class TestBottomUpDeletionStillWorks(ProtectedRelationTestBase):
    """PROTECT defers deletion, it does not forbid it."""

    def test_the_whole_chain_can_be_removed_from_the_bottom(self) -> None:
        self.certificate.delete()
        self.course_attendee.delete()
        self.attendee.delete()
        self.course.delete()

        # With the courses gone, the course's parents are free again.
        self.training_center.delete()
        self.course_convener.delete()
        self.course_type.delete()

        self.organisation.delete()

        self.assertFalse(
            CertifyingOrganisation.objects.filter(
                pk=self.organisation.pk).exists())
        self.assertEqual(Certificate.objects.count(), 0)
