# coding=utf-8
"""Authorisation on the attendee create, update and CSV upload views.

All three carried LoginRequiredMixin only. Each read the organisation slug
from the URL and acted on it without asking whether the requesting user was
entitled to. AttendeeUpdateView was the worst of the three: with no
get_queryset() override, get_object() selected from every attendee in the
system by the sequential primary key in the URL, and both attendee forms
listed certifying_organisation in Meta.fields behind a HiddenInput - a
display choice, not a server-side constraint - so a POST could also move
another organisation's attendee into the attacker's own.
"""

import io
import logging

from certification.models import Attendee
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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


@override_settings(VALID_DOMAIN=['testserver', ])
class AttendeePermissionTest(TestCase):
    """Two organisations, and users with rights over only one of them."""

    def setUp(self) -> None:
        self.client = Client()
        self.client.post('/set_language/', data={'language': 'en'})
        logging.disable(logging.CRITICAL)

        self.project = ProjectF.create()
        self.victim_organisation = self.make_organisation()
        self.attacker_organisation = self.make_organisation()

        self.victim_course = self.make_course(self.victim_organisation)
        self.attacker_course = self.make_course(self.attacker_organisation)

        self.victim_attendee = AttendeeF.create(
            certifying_organisation=self.victim_organisation,
            firstname='Real',
            surname='Person',
            email='real.person@example.com',
        )
        CourseAttendeeF.create(
            course=self.victim_course, attendee=self.victim_attendee)

        self.attacker = self.make_user('attacker')
        self.attacker_organisation.organisation_owners.add(self.attacker)
        self.outsider = self.make_user('outsider')
        self.victim_owner = self.make_user('victimowner')
        self.victim_organisation.organisation_owners.add(self.victim_owner)

    def make_organisation(self):
        return CertifyingOrganisationF.create(
            project=self.project, organisation_credits=10)

    def make_course(self, organisation):
        return CourseF.create(
            certifying_organisation=organisation,
            training_center=TrainingCenterF.create(
                certifying_organisation=organisation),
            course_convener=CourseConvenerF.create(
                certifying_organisation=organisation),
            course_type=CourseTypeF.create(
                certifying_organisation=organisation),
        )

    def make_user(self, username: str, **kwargs: object):
        user = UserF.create(username=username, **kwargs)
        user.set_password('password')
        user.save()
        return user

    def login(self, username: str) -> None:
        self.assertTrue(
            self.client.login(username=username, password='password'))

    def update_url(self, organisation, course, attendee) -> str:
        return reverse('attendee-update', kwargs={
            'organisation_slug': organisation.slug,
            'course_slug': course.slug,
            'pk': attendee.pk,
        })

    def create_url(self, organisation, course) -> str:
        return reverse('attendee-create', kwargs={
            'organisation_slug': organisation.slug,
            'slug': course.slug,
        })

    def upload_url(self, organisation, course) -> str:
        return reverse('upload-attendee', kwargs={
            'organisation_slug': organisation.slug,
            'slug': course.slug,
        })

    def csv_file(self, body: str, name: str = 'attendees.csv'):
        return SimpleUploadedFile(
            name, body.encode('utf-8'), content_type='text/csv')

    # ------------------------------------------------------------------
    # AttendeeUpdateView
    # ------------------------------------------------------------------

    def test_anonymous_cannot_open_the_update_form(self) -> None:
        response = self.client.get(self.update_url(
            self.victim_organisation, self.victim_course,
            self.victim_attendee))

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_outsider_cannot_update_another_organisations_attendee(
            self) -> None:
        """The regression: any account could rewrite any attendee."""

        self.login('outsider')
        response = self.client.post(
            self.update_url(
                self.victim_organisation, self.victim_course,
                self.victim_attendee),
            data={
                'firstname': 'Pwned',
                'surname': 'Pwned',
                'email': 'attacker@evil.test',
            })

        self.assertEqual(response.status_code, 403)
        self.victim_attendee.refresh_from_db()
        self.assertEqual(self.victim_attendee.firstname, 'Real')
        self.assertEqual(self.victim_attendee.email, 'real.person@example.com')

    def test_attendee_of_another_organisation_is_not_reachable(self) -> None:
        """Pairing your own organisation slug with a foreign attendee pk.

        The attacker owns attacker_organisation, so the permission check
        passes; the queryset scoping is what has to stop this.
        """

        self.login('attacker')
        response = self.client.post(
            self.update_url(
                self.attacker_organisation, self.attacker_course,
                self.victim_attendee),
            data={
                'firstname': 'Pwned',
                'surname': 'Pwned',
                'email': 'attacker@evil.test',
            })

        self.assertEqual(response.status_code, 404)
        self.victim_attendee.refresh_from_db()
        self.assertEqual(self.victim_attendee.firstname, 'Real')

    def test_owner_can_update_their_own_attendee(self) -> None:
        self.login('victimowner')
        response = self.client.post(
            self.update_url(
                self.victim_organisation, self.victim_course,
                self.victim_attendee),
            data={
                'firstname': 'Updated',
                'surname': 'Person',
                'email': 'real.person@example.com',
            })

        self.assertEqual(response.status_code, 302)
        self.victim_attendee.refresh_from_db()
        self.assertEqual(self.victim_attendee.firstname, 'Updated')

    def test_update_cannot_move_attendee_to_another_organisation(self) -> None:
        """The hidden field was never a constraint."""

        self.login('victimowner')
        self.client.post(
            self.update_url(
                self.victim_organisation, self.victim_course,
                self.victim_attendee),
            data={
                'firstname': 'Updated',
                'surname': 'Person',
                'email': 'real.person@example.com',
                'certifying_organisation': self.attacker_organisation.pk,
            })

        self.victim_attendee.refresh_from_db()
        self.assertEqual(
            self.victim_attendee.certifying_organisation_id,
            self.victim_organisation.pk)

    # ------------------------------------------------------------------
    # AttendeeCreateView
    # ------------------------------------------------------------------

    def test_outsider_cannot_create_attendee_in_another_organisation(
            self) -> None:
        self.login('outsider')
        before = Attendee.objects.count()

        response = self.client.post(
            self.create_url(self.victim_organisation, self.victim_course),
            data={
                'firstname': 'Injected',
                'surname': 'Attendee',
                'email': 'injected@evil.test',
            })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attendee.objects.count(), before)

    def test_owner_can_create_attendee(self) -> None:
        self.login('victimowner')
        response = self.client.post(
            self.create_url(self.victim_organisation, self.victim_course),
            data={
                'firstname': 'New',
                'surname': 'Attendee',
                'email': 'new.attendee@example.com',
            })

        self.assertEqual(response.status_code, 302)
        created = Attendee.objects.get(email='new.attendee@example.com')
        self.assertEqual(
            created.certifying_organisation_id, self.victim_organisation.pk)

    def test_create_ignores_a_supplied_organisation(self) -> None:
        """The organisation comes from the URL, not from the POST body."""

        self.login('victimowner')
        self.client.post(
            self.create_url(self.victim_organisation, self.victim_course),
            data={
                'firstname': 'New',
                'surname': 'Attendee',
                'email': 'forced@example.com',
                'certifying_organisation': self.attacker_organisation.pk,
            })

        created = Attendee.objects.get(email='forced@example.com')
        self.assertEqual(
            created.certifying_organisation_id, self.victim_organisation.pk)

    # ------------------------------------------------------------------
    # CsvUploadView
    # ------------------------------------------------------------------

    def test_outsider_cannot_upload_into_another_organisation(self) -> None:
        self.login('outsider')
        before = Attendee.objects.count()

        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={'file': self.csv_file(
                'firstname,surname,email\nA,B,a.b@evil.test\n')})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attendee.objects.count(), before)

    def test_anonymous_cannot_upload(self) -> None:
        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={'file': self.csv_file(
                'firstname,surname,email\nA,B,a.b@evil.test\n')})

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_owner_can_upload(self) -> None:
        self.login('victimowner')
        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={'file': self.csv_file(
                'firstname,surname,email\nCsv,Person,csv.person@example.com\n'
            )})

        self.assertEqual(response.status_code, 302)
        created = Attendee.objects.get(email='csv.person@example.com')
        self.assertEqual(
            created.certifying_organisation_id, self.victim_organisation.pk)

    def test_upload_without_a_file_does_not_crash(self) -> None:
        """seek() was called on the file before it was known to exist."""

        self.login('victimowner')
        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={})

        self.assertEqual(response.status_code, 200)

    def test_upload_with_too_few_columns_does_not_crash(self) -> None:
        """Rows are read positionally, so this used to raise IndexError."""

        self.login('victimowner')
        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={'file': self.csv_file('firstname,surname\nA,B\n')})

        self.assertEqual(response.status_code, 200)

    def test_upload_is_capped(self) -> None:
        body = io.StringIO()
        body.write('firstname,surname,email\n')
        for index in range(1001):
            body.write('First%d,Last%d,person%d@example.com\n' % (
                index, index, index))

        self.login('victimowner')
        before = Attendee.objects.count()
        response = self.client.post(
            self.upload_url(self.victim_organisation, self.victim_course),
            data={'file': self.csv_file(body.getvalue())})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendee.objects.count(), before)

    def test_upload_targets_the_course_of_the_named_organisation(self) -> None:
        """A foreign course slug must not be reachable via your own org."""

        self.login('attacker')
        before = Attendee.objects.count()

        response = self.client.post(
            reverse('upload-attendee', kwargs={
                'organisation_slug': self.attacker_organisation.slug,
                'slug': self.victim_course.slug,
            }),
            data={'file': self.csv_file(
                'firstname,surname,email\nA,B,a.b@evil.test\n')})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Attendee.objects.count(), before)
