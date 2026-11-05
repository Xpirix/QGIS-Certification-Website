from django.test import TestCase

from certification.models import Course
from certification.serializers.course_serializer import CourseSerializer
from certification.tests.model_factories import (
    CourseF,
    CourseTypeF,
    CertifyingOrganisationF,
    CourseConvenerF,
    TrainingCenterF,
    ProjectF,
)


class TestSerializer(TestCase):
    """Test certifying organisation serializer."""

    def test_course_serializer(self):
        project = ProjectF.create(certificate_credit=3)
        certifying_organisation = \
            CertifyingOrganisationF.create(
                project=project, organisation_credits=10)
        training_center = TrainingCenterF.create(
            certifying_organisation=certifying_organisation)
        course_convener = CourseConvenerF.create(
            certifying_organisation=certifying_organisation)
        course_type = CourseTypeF.create(
            name='test_course_type',
            certifying_organisation=certifying_organisation)
        course = CourseF.create(
            certifying_organisation=certifying_organisation,
            training_center=training_center,
            course_convener=course_convener,
            course_type=course_type
        )
        serializer = CourseSerializer(course, many=False)
        serializer_data = dict(
            serializer.data['properties']
        )
        self.assertEqual(
            serializer_data['course_type_name'],
            'test_course_type'
        )

    def make_course(self, coursetype_link: str = '', **course_fields: str) -> Course:
        certifying_organisation = CertifyingOrganisationF.create(
            project=ProjectF.create())
        return CourseF.create(
            certifying_organisation=certifying_organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=certifying_organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=certifying_organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=certifying_organisation,
                coursetype_link=coursetype_link),
            **course_fields,
        )

    def test_course_type_link(self) -> None:
        course = self.make_course(
            coursetype_link='https://example.com/qgis-basics')
        properties = CourseSerializer(course).data['properties']
        self.assertEqual(
            properties['course_type_link'], 'https://example.com/qgis-basics')

    def test_course_type_link_is_null_without_a_link(self) -> None:
        properties = CourseSerializer(self.make_course()).data['properties']
        self.assertIsNone(properties['course_type_link'])
