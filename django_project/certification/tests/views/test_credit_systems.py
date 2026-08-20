# coding=utf-8

from django.test import TestCase
from django.test.client import Client
from core.model_factories import UserF
from base.tests.model_factories import ProjectF
from certification.tests.model_factories import (
    CourseF,
    CertifyingOrganisationF,
    CourseAttendeeF,
    CourseTypeF,
    AttendeeF,
    CourseConvenerF,
    CertificateTypeF,
    TrainingCenterF,)
from certification.views import CertificateCreateView
from certification.forms import CertificateForm
from certification.models import Certificate


class TestCreditSystems(TestCase):
    """Test the credit systems in the certification."""

    def setUp(self):
        """
        In this test, a certificate is cost 3 credit.

        """

        self.project = ProjectF.create(certificate_credit=3)
        self.certifying_organisation = \
            CertifyingOrganisationF.create(
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
            course_type=self.course_type
        )

        self.certificate_type = CertificateTypeF.create()

        self.client = Client()
        self.client.post(
            '/set_language/', data={'language': 'en'})
        self.user = UserF.create(**{
            'username': 'anita',
            'is_staff': True
        })
        self.user.set_password('password')
        self.user.save()

    def tearDown(self):
        pass

    def test_issue_certificate_with_credit(self):
        """
        Test issue certificate when organisation is set to have 10 credits.

        """

        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_attendee = CourseAttendeeF.create(
            attendee=attendee,
            course=self.course
        )

        # Issue certificate
        certificate_create = \
            CertificateCreateView(
                project_slug=self.project.slug,
                organisation_slug=self.certifying_organisation.slug,
                # Normally set by CourseEditPermissionMixin.dispatch();
                # supplied here because this test calls form_valid()
                # directly rather than going through the view.
                certifying_organisation=self.certifying_organisation,
                course_slug=self.course.slug)
        form = \
            CertificateForm(
                user=self.user,
                course=self.course,
                attendee=self.course_attendee.attendee,
                certificate_type=self.certificate_type,
            )

        response = certificate_create.form_valid(form)
        is_paid = form['is_paid'].value()
        self.assertEqual(response.status_code, 302)

        # Newly created object test
        certificate = \
            Certificate.objects.get(attendee=self.course_attendee.attendee)
        certificate.is_paid = is_paid

        # Test remaining credits in the organisation
        self.assertEqual(
            certificate.course.certifying_organisation.organisation_credits, 7)

        # Test status of the certificate
        self.assertEqual(certificate.is_paid, True)

        # Add another attendee

        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation
        )
        course_attendee2 = CourseAttendeeF.create(
            course=self.course,
            attendee=attendee
        )

        # Issue another certificate
        certificate_create = \
            CertificateCreateView(
                project_slug=self.project.slug,
                organisation_slug=self.certifying_organisation.slug,
                # Normally set by CourseEditPermissionMixin.dispatch();
                # supplied here because this test calls form_valid()
                # directly rather than going through the view.
                certifying_organisation=self.certifying_organisation,
                course_slug=self.course.slug)
        form2 = \
            CertificateForm(
                user=self.user,
                course=self.course,
                attendee=course_attendee2.attendee,
                certificate_type=self.certificate_type,
            )
        response = certificate_create.form_valid(form2)
        is_paid = form2['is_paid'].value()
        self.assertEqual(response.status_code, 302)

        # Newly created object test
        certificate2 = \
            Certificate.objects.get(attendee=course_attendee2.attendee)
        certificate2.is_paid = is_paid

        self.assertEqual(
            certificate2.course.certifying_organisation.organisation_credits,
            4)
        self.assertEqual(certificate2.is_paid, True)

    def test_issue_certificate_without_credit(self):
        """Test when the organisation has no credit available."""

        # The organisation credit is set to 0
        certifying_organisation = \
            CertifyingOrganisationF.create(
                project=self.project, organisation_credits=0)
        training_center = TrainingCenterF.create(
            certifying_organisation=certifying_organisation)
        course_convener = CourseConvenerF.create(
            certifying_organisation=certifying_organisation)
        course_type = CourseTypeF.create(
            certifying_organisation=certifying_organisation)
        course = CourseF.create(
            certifying_organisation=certifying_organisation,
            training_center=training_center,
            course_convener=course_convener,
            course_type=course_type
        )

        attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_attendee = CourseAttendeeF.create(
            attendee=attendee,
            course=course
        )

        # Issue certificate
        certificate_create = \
            CertificateCreateView(
                project_slug=self.project.slug,
                organisation_slug=certifying_organisation.slug,
                # Normally set by CourseEditPermissionMixin.dispatch();
                # supplied here because this test calls form_valid()
                # directly rather than going through the view.
                certifying_organisation=certifying_organisation,
                course_slug=course.slug)
        form = \
            CertificateForm(
                user=self.user,
                course=course,
                attendee=self.course_attendee.attendee,
                certificate_type=self.certificate_type,
            )

        response = certificate_create.form_valid(form)
        is_paid = form['is_paid'].value()
        self.assertEqual(response.status_code, 302)

        # Newly created object test
        certificate = \
            Certificate.objects.get(attendee=self.course_attendee.attendee)
        certificate.is_paid = is_paid

        self.assertEqual(
            certificate.course.certifying_organisation.organisation_credits,
            -3)
        self.assertEqual(certificate.is_paid, False)
