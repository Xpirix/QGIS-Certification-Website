# coding=utf-8
import datetime

from certification.models import Course
from certification.tests.model_factories import (
    CertifyingOrganisationF,
    CourseConvenerF,
    CourseF,
    CourseTypeF,
    ProjectF,
    TrainingCenterF,
)
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


class TestHomepageCourses(TestCase):
    """Test the courses coming soon on the home page."""

    @override_settings(VALID_DOMAIN=['testserver'])
    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=ProjectF.create()
        )
        self.training_center = TrainingCenterF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_convener = CourseConvenerF.create(
            certifying_organisation=self.certifying_organisation
        )

    @override_settings(VALID_DOMAIN=['testserver'])
    def test_home_page_leaves_out_closed_courses(self) -> None:
        self.make_course('Open workshop', is_open=True)
        self.make_course('Closed module', is_open=False)

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Open workshop')
        self.assertNotContains(response, 'Closed module')

    @override_settings(VALID_DOMAIN=['testserver'])
    def test_home_page_shows_the_modality(self) -> None:
        self.make_course('Open workshop', modality=Course.Modality.HYBRID)

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Hybrid')

    def make_course(
        self,
        course_type_name: str,
        is_open: bool = True,
        modality: str = '',
    ) -> Course:
        course_type = CourseTypeF.create(
            name=course_type_name,
            certifying_organisation=self.certifying_organisation,
        )
        next_week = datetime.date.today() + datetime.timedelta(days=7)
        return CourseF.create(
            certifying_organisation=self.certifying_organisation,
            training_center=self.training_center,
            course_convener=self.course_convener,
            course_type=course_type,
            start_date=next_week,
            end_date=next_week + datetime.timedelta(days=1),
            is_open=is_open,
            modality=modality,
        )
