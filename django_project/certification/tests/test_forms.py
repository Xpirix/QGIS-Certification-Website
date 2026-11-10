from django.contrib.gis.geos import Point
from django.test import TestCase

from base.tests.model_factories import ProjectF
from certification.tests.model_factories import (
    CertifyingOrganisationF, CourseConvenerF, CourseTypeF,
    ProjectCertificateTypeF, StatusF, TrainingCenterF, ChecklistF
)
from certification.models import (
    ORGANIZATION_OWNER, CertifyingOrganisation, Course, Checklist, OrganisationChecklist
)
from core.model_factories import UserF
from certification.forms import (
    CertifyingOrganisationForm, CourseConvenerForm, CourseForm,
    TrainingCenterForm
)


class TestCertifyingOrganisationForm(TestCase):

    def setUp(self):
        self.user = UserF.create(**{
            'username': 'admin',
            'password': 'password',
            'is_staff': True
        })
        self.project = ProjectF.create()
        self.status = StatusF.create(
            name='pending',
            project=self.project
        )
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project,
            approved=False,
            rejected=False,
            status=self.status
        )
        self.certifying_organisation.organisation_owners.set([self.user])
        self.user.set_password('password')
        self.user.save()
        self.client.login(username='admin', password='password')

    def test_update_form(self):
        form_title = 'Update form'
        form = CertifyingOrganisationForm(
            user=self.user,
            project=self.project,
            form_title=form_title,
            show_owner_message=True
        )
        self.assertEqual(
            form.helper.layout.fields[0].legend,
            form_title
        )
        self.assertEqual(
            form.fields['owner_message'].label,
            'Message to validator'
        )
        self.assertFalse(form.is_valid())

        data = {
            'name': 'Updated organisation',
            'organisation_email': 'test@test.com',
            'address': 'Address',
            'organisation_phone': '12121212',
            'organisation_owners': [self.user.id],
            'owner_message': 'test',
            'project': self.project.id
        }
        form = CertifyingOrganisationForm(
            instance=self.certifying_organisation,
            user=self.user,
            project=self.project,
            form_title=form_title,
            show_owner_message=True,
            data=data
        )
        self.assertTrue(form.is_valid())
        form.save()
        certifying_organisation = (
            CertifyingOrganisation.objects.get(
                id=self.certifying_organisation.id
            )
        )
        self.assertEqual(
            certifying_organisation.status,
            None
        )


class TestUserPickerWidgets(TestCase):
    """The user pickers must not dump the whole user directory into HTML."""

    def setUp(self):
        self.owner = UserF.create(username='owner')
        self.other = UserF.create(username='stranger')
        self.project = ProjectF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project)

    def test_owner_widget_only_renders_selected_user(self):
        form = CertifyingOrganisationForm(
            user=self.owner, project=self.project)
        html = str(form['organisation_owners'])
        # The creating user is pre-selected and should appear...
        self.assertIn('owner', html)
        # ...but an unrelated user must not be dumped into the options.
        self.assertNotIn('stranger', html)

    def test_convener_widget_renders_no_users_by_default(self):
        form = CourseConvenerForm(
            user=self.owner,
            certifying_organisation=self.certifying_organisation)
        html = str(form['user'])
        self.assertNotIn('owner', html)
        self.assertNotIn('stranger', html)


class TestCourseForm(TestCase):

    def setUp(self) -> None:
        self.user = UserF.create()
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=ProjectF.create())
        self.certificate_type = ProjectCertificateTypeF.create(
            project=self.certifying_organisation.project).certificate_type

    def form(self, **data: str | int) -> CourseForm:
        return CourseForm(
            data=data or None,
            user=self.user,
            certifying_organisation=self.certifying_organisation,
        )

    def test_new_courses_start_open(self) -> None:
        self.assertTrue(self.form()['is_open'].value())

    def test_modality_is_required(self) -> None:
        form = self.form(language='English')
        self.assertFalse(form.is_valid())
        self.assertIn('modality', form.errors)

    def test_form_saves_modality_and_is_open(self) -> None:
        organisation = self.certifying_organisation
        form = self.form(
            course_type=CourseTypeF.create(
                certifying_organisation=organisation).pk,
            course_convener=CourseConvenerF.create(
                certifying_organisation=organisation).pk,
            training_center=TrainingCenterF.create(
                certifying_organisation=organisation).pk,
            modality=Course.Modality.ONLINE,
            language='English',
            trained_competence='Map making',
            start_date='2026-12-01',
            end_date='2026-12-02',
            certifying_organisation=organisation.pk,
            certificate_type=self.certificate_type.pk,
        )
        self.assertTrue(form.is_valid(), form.errors)
        course = form.save()
        self.assertEqual(course.modality, 'online')
        self.assertFalse(course.is_open)


class TestCertifyingOrganisationChecklist(TestCase):
    """The applicant checklist is answered in full, with links where asked."""

    def setUp(self):
        self.user = UserF.create(username='applicant')
        self.project = ProjectF.create()
        self.question = ChecklistF.create(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True,
            show_text_box=True,
            link_required=True
        )

    def questions(self):
        return Checklist.objects.filter(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True
        )

    def build_form(self, answers, questions=None):
        data = {
            'name': 'New organisation',
            'organisation_email': 'test@test.com',
            'address': 'Address',
            'organisation_phone': '12121212',
            'organisation_owners': [self.user.id],
            'project': self.project.id
        }
        data.update(answers)
        return CertifyingOrganisationForm(
            user=self.user,
            project=self.project,
            checklist_questions=questions,
            data=data
        )

    def test_yes_needs_the_text_box_filled(self):
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'yes',
                f'textarea-{self.question.id}': ''
            },
            questions=self.questions()
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.checklist_errors[str(self.question.id)],
            'Tell us what you did.'
        )
        self.assertIn(
            'Look at the questions below.',
            form.non_field_errors()[0]
        )

    def test_yes_needs_links_rather_than_prose(self):
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'yes',
                f'textarea-{self.question.id}': 'I wrote some documentation'
            },
            questions=self.questions()
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.checklist_errors[str(self.question.id)],
            'Add at least one URL.'
        )

    def test_yes_with_links_is_accepted_and_stored(self):
        links = (
            'https://github.com/qgis/QGIS/pull/1\n'
            'http://docs.qgis.org/latest/en/docs/'
        )
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'yes',
                f'textarea-{self.question.id}': links
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())
        organisation = form.save()

        answer = OrganisationChecklist.objects.get(
            organisation=organisation,
            checklist=self.question
        )
        self.assertTrue(answer.checked)
        self.assertEqual(answer.text_box_content, links)
        self.assertEqual(answer.submitter, self.user)
        self.assertEqual(answer.checklist_question, self.question.question)

    def test_no_does_not_need_the_text_box(self):
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'no',
                f'textarea-{self.question.id}': ''
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())
        organisation = form.save()
        self.assertFalse(
            OrganisationChecklist.objects.get(
                organisation=organisation,
                checklist=self.question
            ).checked
        )

    def test_a_question_without_a_text_box_needs_no_links(self):
        plain_question = ChecklistF.create(
            project=self.project,
            target=ORGANIZATION_OWNER,
            active=True,
            show_text_box=False
        )
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'no',
                f'checklist-{plain_question.id}': 'yes'
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())

    def test_an_unanswered_question_is_rejected(self):
        form = self.build_form({}, questions=self.questions())
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.checklist_errors[str(self.question.id)],
            'Answer yes or no.'
        )

    def test_an_answer_we_did_not_ask_for_is_ignored(self):
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'no',
                'checklist-999999': 'yes',
                'checklist-not-a-number': 'yes'
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())
        organisation = form.save()
        self.assertEqual(
            OrganisationChecklist.objects.filter(
                organisation=organisation
            ).count(),
            1
        )

    def test_a_form_without_questions_skips_the_checklist(self):
        form = self.build_form({})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.checklist_errors, {})

    def test_yes_accepts_a_link_inside_prose(self):
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'yes',
                f'textarea-{self.question.id}': (
                    'We rewrote the install guide, see '
                    'https://docs.qgis.org/latest/en/docs/ for the result.'
                )
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())

    def test_a_question_that_wants_no_link_accepts_prose(self):
        self.question.link_required = False
        self.question.save()
        form = self.build_form(
            {
                f'checklist-{self.question.id}': 'yes',
                f'textarea-{self.question.id}': 'We ran a training course'
            },
            questions=self.questions()
        )
        self.assertTrue(form.is_valid())


class TestTrainingCenterForm(TestCase):
    """The location picker gets the map data and saves the picked point."""

    def setUp(self) -> None:
        self.user = UserF.create()
        self.organisation = CertifyingOrganisationF.create(
            project=ProjectF.create(), country='MG')

    def form(self, **kwargs: object) -> TrainingCenterForm:
        return TrainingCenterForm(
            user=self.user,
            certifying_organisation=self.organisation,
            **kwargs,
        )

    def details(self, location: str) -> dict[str, str]:
        return {
            'name': 'Antananarivo centre',
            'email': 'centre@example.org',
            'address': 'Lot 1, Antananarivo',
            'phone': '+261200000000',
            'location': location,
        }

    def test_picker_frames_the_organisation_country(self) -> None:
        html = str(self.form()['location'])
        self.assertIn('data-map="location"', html)
        self.assertIn('"input": "id_location"', html)
        self.assertIn('"country": "MG"', html)

    def test_picker_shows_the_saved_location(self) -> None:
        center = TrainingCenterF.create(
            certifying_organisation=self.organisation,
            location=Point(x=47.5, y=-18.5, srid=4326),
        )
        html = str(self.form(instance=center)['location'])
        self.assertIn('value="POINT (47.5 -18.5)"', html)

    def test_picked_point_is_saved_in_longitude_and_latitude(self) -> None:
        form = self.form(data=self.details('POINT(47.5 -18.9)'))
        self.assertTrue(form.is_valid(), form.errors)
        center = form.save()
        center.refresh_from_db()
        self.assertEqual(center.location.srid, 4326)
        self.assertEqual((center.location.x, center.location.y), (47.5, -18.9))

    def test_removed_location_saves_none(self) -> None:
        form = self.form(data=self.details(''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().location)
