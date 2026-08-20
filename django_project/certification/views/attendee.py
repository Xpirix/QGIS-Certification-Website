# coding=utf-8
import io
import csv

from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (
    CreateView, FormView, UpdateView)
from braces.views import LoginRequiredMixin, FormMessagesMixin
from certification.models import (
    Attendee, CourseAttendee, Course, Certificate
)
from certification.forms import (
    AttendeeForm, CsvAttendeeForm, UpdateAttendeeForm)
from certification.mixins import CourseEditPermissionMixin


class AttendeeMixin(object):
    """Mixin class to provide standard settings for Attendee."""

    model = Attendee
    form_class = AttendeeForm


class AttendeeCreateView(
        LoginRequiredMixin,
        CourseEditPermissionMixin,
        AttendeeMixin,
        CreateView):
    """Create view for Attendee.

    CourseEditPermissionMixin resolves the organisation named in the URL and
    refuses the request unless the user may act on it. Without it any account
    could add attendees to any organisation's course, since the slug was read
    from the URL and used without being checked against the requester.
    """

    context_object_name = 'attendee'
    template_name = 'attendee/create.html'

    def get_success_url(self):
        """Define the redirect URL.

        After successful creation of the object, the User will be redirected
        to the create course attendee page.

       :returns: URL
       :rtype: HttpResponse
       """
        add_to_course = self.request.POST.get('add_to_course')
        if add_to_course is None:
            success_url = reverse('courseattendee-create', kwargs={
                'organisation_slug': self.organisation_slug,
                'slug': self.course_slug,
            })
        else:
            success_url = reverse('course-detail', kwargs={
                'organisation_slug': self.organisation_slug,
                'slug': self.course_slug,
            })
        return success_url

    def get_context_data(self, **kwargs):
        """Get the context data which is passed to a template.

        :param kwargs: Any arguments to pass to the superclass.
        :type kwargs: dict

        :returns: Context data which will be passed to the template.
        :rtype: dict
        """

        context = super(
            AttendeeCreateView, self).get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        """Get keyword arguments from form.

        :returns keyword argument from the form
        :rtype: dict
        """

        # organisation_slug and certifying_organisation are set by
        # CourseEditPermissionMixin.dispatch(), before any of this runs.
        kwargs = super(AttendeeCreateView, self).get_form_kwargs()
        self.project_slug = 'qgis'
        self.course_slug = self.kwargs.get('slug', None)
        kwargs.update({
            'user': self.request.user,
            'certifying_organisation': self.certifying_organisation
        })
        return kwargs

    def form_valid(self, form):
        add_to_course = self.request.POST.get('add_to_course')
        if add_to_course is None:
            if form.is_valid():
                form.save()
        else:
            if form.is_valid():
                object = form.save()
                course_slug = self.kwargs.get('slug', None)
                # Scoped to the organisation, so that permission granted for
                # this organisation cannot be spent on another one's course
                # by pairing the two slugs.
                course = get_object_or_404(
                    Course,
                    slug=course_slug,
                    certifying_organisation=self.certifying_organisation)
                course_attendee = CourseAttendee(
                    attendee=object,
                    course=course,
                    author=self.request.user
                )
                course_attendee.save()
        return super(AttendeeCreateView, self).form_valid(form)


class CsvUploadView(
        FormMessagesMixin,
        LoginRequiredMixin,
        CourseEditPermissionMixin,
        FormView):
    """
    Allow upload of attendees through CSV file.

    This endpoint writes an unbounded number of rows into the organisation
    named in the URL, so it needs the same permission check as the rest of
    the course views rather than only requiring a login.
    """

    context_object_name = 'csvupload'
    form_class = CsvAttendeeForm
    template_name = 'attendee/upload_attendee_csv.html'

    # A CSV of attendees is a class list, not a dataset. The cap is here to
    # bound what a single request can insert.
    maximum_rows = 1000

    # FormMessagesMixin raises ImproperlyConfigured if these are unset, and
    # they were previously only assigned inside the success path - so any
    # invalid submission, including simply not choosing a file, produced a
    # 500 rather than the form again. The success path still overrides
    # form_valid_message with the row counts.
    form_valid_message = 'The attendees were uploaded.'
    form_invalid_message = (
        'Something went wrong while running the upload. Please check the '
        'file and try again.')

    def get_success_url(self):
        """Define the redirect URL.

        After successful creation of the object, the User will be redirected
        to the Course detail page.

       :returns: URL
       :rtype: HttpResponse
       """

        return reverse('course-detail', kwargs={
            'organisation_slug': self.organisation_slug,
            'slug': self.slug,
        })

    def get_context_data(self, **kwargs):
        """Get the context data which is passed to a template.

        :param kwargs: Any arguments to pass to the superclass.
        :type kwargs: dict

        :returns: Context data which will be passed to the template.
        :rtype: dict
        """

        context = super(
            CsvUploadView, self).get_context_data(**kwargs)
        context['certifyingorganisation'] = self.certifying_organisation
        context['course'] = self.get_course()
        return context

    def get_course(self) -> Course:
        """Resolve the course, within the organisation named in the URL.

        Looking the course up by slug alone would let a user with rights over
        one organisation upload into another organisation's course by pairing
        their own organisation slug with a foreign course slug.

        :returns: The course this upload targets.
        :rtype: Course
        """

        self.slug = self.kwargs.get('slug', None)
        return get_object_or_404(
            Course,
            slug=self.slug,
            certifying_organisation=self.certifying_organisation)

    def get_form_kwargs(self):
        """Get keyword arguments from form.

        :returns keyword argument from the form
        :rtype: dict
        """

        # organisation_slug and certifying_organisation come from
        # CourseEditPermissionMixin.dispatch().
        kwargs = super(CsvUploadView, self).get_form_kwargs()
        self.project_slug = 'qgis'
        self.slug = self.kwargs.get('slug', None)
        self.course = self.get_course()
        return kwargs

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        """Get form instance from upload.

           After successful creation of the object,the User
           will be redirected to the create course attendee page.

          :returns: URL
          :rtype: HttpResponse
        """
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        attendees_file = request.FILES.get('file')
        course = self.get_course()
        if form.is_valid():
            if attendees_file:
                attendees_file.seek(0)
                try:
                    contents = attendees_file.read().decode('utf-8')
                except UnicodeDecodeError:
                    self.form_invalid_message = (
                        'That file is not valid UTF-8 text. Please save the '
                        'spreadsheet as a UTF-8 CSV and try again.')
                    return self.form_invalid(form)

                reader = csv.DictReader(io.StringIO(contents))
                fieldnames = reader.fieldnames
                # Rows are read positionally, so a file with fewer than three
                # columns used to raise IndexError and return a 500.
                if not fieldnames or len(fieldnames) < 3:
                    self.form_invalid_message = (
                        'The CSV needs at least three columns: first name, '
                        'surname and email address.')
                    return self.form_invalid(form)

                rows = list(reader)
                if len(rows) > self.maximum_rows:
                    self.form_invalid_message = (
                        'That file has {} rows; this form accepts at most '
                        '{} at a time.'.format(len(rows), self.maximum_rows))
                    return self.form_invalid(form)

                attendee_count = 0
                course_attendee_count = 0
                existing_attendee_count = 0
                for row in rows:
                    # We should have logic here to first see if the attendee
                    # already exists and if they do, just add them to the
                    # course
                    try:
                        attendee = Attendee.objects.get(
                            firstname=row[fieldnames[0]],
                            surname=row[fieldnames[1]],
                            email=row[fieldnames[2]],
                            certifying_organisation=
                            self.certifying_organisation,
                        )
                    except Attendee.DoesNotExist:
                        attendee = Attendee(
                            firstname=row[fieldnames[0]],
                            surname=row[fieldnames[1]],
                            email=row[fieldnames[2]],
                            certifying_organisation=
                            self.certifying_organisation,
                            author=self.request.user
                        )
                        attendee.save()
                        attendee_count += 1

                    try:
                        course_attendee = CourseAttendee.objects.get(
                            attendee=attendee,
                            course=course,
                        )
                    except CourseAttendee.DoesNotExist:
                        course_attendee = CourseAttendee(
                            attendee=attendee,
                            course=course,
                            author=self.request.user
                        )
                        course_attendee.save()
                        course_attendee_count += 1
                    else:
                        existing_attendee_count += 1

                self.form_valid_message = (
                    'From the csv: {} attendee already exist in this course, '
                    '{} new attendees were created, and {} attendees were '
                    'added to the course: {}'.format(
                        existing_attendee_count,
                        attendee_count,
                        course_attendee_count,
                        self.course)
                )

                self.form_invalid_message = (
                    'Something wrong happened while running the upload. '
                    'Please contact site support to help resolving the issue.')
            return self.form_valid(form)

        else:
            return self.form_invalid(form)


class AttendeeUpdateView(
        LoginRequiredMixin,
        CourseEditPermissionMixin,
        UpdateView):
    """View for updating attendee."""

    context_object_name = 'attendee'
    template_name = 'attendee/update.html'
    model = Attendee
    form_class = UpdateAttendeeForm

    def get_queryset(self) -> QuerySet:
        """Restrict lookups to attendees of the organisation in the URL.

        Without this, get_object() selected from every attendee in the system
        by the primary key in the URL, and those keys are sequential - so the
        whole attendee table, every trainee's name and email address, could be
        walked and rewritten by any account.

        :returns: Attendees belonging to this certifying organisation.
        :rtype: QuerySet
        """

        return Attendee.objects.filter(
            certifying_organisation=self.certifying_organisation)

    def get_success_url(self):
        """Define the redirect URL.

        After successful updating the object, the User will be redirected
        to the course detail page.

       :returns: URL
       :rtype: HttpResponse
       """

        return reverse('course-detail', kwargs={
            'organisation_slug': self.organisation_slug,
            'slug': self.course_slug,
        })

    def get_context_data(self, **kwargs):
        """Get the context data which is passed to a template.

        :param kwargs: Any arguments to pass to the superclass.
        :type kwargs: dict

        :returns: Context data which will be passed to the template.
        :rtype: dict
        """

        context = super(
            AttendeeUpdateView, self).get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        """Get keyword arguments from form.

        :returns keyword argument from the form
        :rtype: dict
        """

        # organisation_slug and certifying_organisation come from
        # CourseEditPermissionMixin.dispatch().
        kwargs = super(AttendeeUpdateView, self).get_form_kwargs()
        self.project_slug = 'qgis'
        self.course_slug = self.kwargs.get('course_slug', None)
        kwargs.update({
            'user': self.request.user,
            'certifying_organisation': self.certifying_organisation
        })
        return kwargs

    def certificate_blocks_editing(self) -> bool:
        """Check whether an issued certificate freezes this attendee.

        :returns: True if the attendee's certificate can no longer be revoked.
        :rtype: bool
        """

        self.course_slug = self.kwargs.get('course_slug', None)
        course = Course.objects.filter(
            slug=self.course_slug,
            certifying_organisation=self.certifying_organisation).first()
        if course is None:
            return False
        certificate = Certificate.objects.filter(
            course=course,
            attendee=self.get_object()
        ).first()
        return certificate is not None and not certificate.is_revocable

    def get(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        if self.certificate_blocks_editing():
            return HttpResponseForbidden('Course is not editable.')
        return super(AttendeeUpdateView, self).get(request, *args, **kwargs)

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        """Apply the same freeze to POST.

        The check used to sit in get() only, so a direct POST skipped it and
        the attendee named on an already-issued certificate could still be
        renamed.
        """

        if self.certificate_blocks_editing():
            return HttpResponseForbidden('Course is not editable.')
        return super(AttendeeUpdateView, self).post(request, *args, **kwargs)
