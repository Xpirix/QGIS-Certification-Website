# coding=utf-8
import datetime
import logging

from certification.models import Course, CourseType
from certification.tests.model_factories import (
    CertificateTypeF,
    CertifyingOrganisationF,
    CourseConvenerF,
    CourseF,
    CourseTypeF,
    ProjectCertificateTypeF,
    ProjectF,
    TrainingCenterF,
    UserF,
)
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


class TestCourseApiView(TestCase):
    """Test that Course API View works."""

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
        self.project = ProjectF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project
        )
        self.training_center = TrainingCenterF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_convener = CourseConvenerF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_type = CourseTypeF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course = CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=self.training_center,
            course_convener=self.course_convener,
            course_type=self.course_type,
        )
        self.certificate_type = CertificateTypeF.create()
        self.project_cert_type = ProjectCertificateTypeF.create(
            project=self.project, certificate_type=self.certificate_type
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

        # Nothing to do: TestCase wraps each test in a transaction and rolls
        # it back, so tearing the fixtures down by hand is redundant. It also
        # cannot work now that the relations are PROTECTed, since it deleted
        # parents before their children.
        pass

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_upcoming_courses_api(self):
        """
        Test the upcoming courses API endpoint.
        """
        response = self.client.get(reverse("feed-upcoming-project-course"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.name)

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_feeds_leave_out_closed_courses(self) -> None:
        other_type = CourseTypeF.create(
            certifying_organisation=self.certifying_organisation
        )
        today = datetime.date.today()
        last_month = today - datetime.timedelta(days=30)
        closed_upcoming = self.make_course(other_type, today, is_open=False)
        closed_past = self.make_course(other_type, last_month, is_open=False)
        open_past = self.make_course(self.course_type, last_month)

        feeds = [
            (reverse("feed-upcoming-project-course"), self.course, closed_upcoming),
            (reverse("feed-past-project-course"), open_past, closed_past),
            (
                reverse(
                    "feed-upcoming-course",
                    kwargs={"organisation_slug": self.certifying_organisation.slug},
                ),
                self.course,
                closed_upcoming,
            ),
        ]
        for url, open_course, closed_course in feeds:
            response = self.client.get(url)
            self.assertContains(response, open_course.name)
            self.assertNotContains(response, closed_course.name)

    def make_course(
        self,
        course_type: CourseType,
        start_date: datetime.date,
        is_open: bool = True,
    ) -> Course:
        return CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=self.training_center,
            course_convener=self.course_convener,
            course_type=course_type,
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=1),
            is_open=is_open,
        )
