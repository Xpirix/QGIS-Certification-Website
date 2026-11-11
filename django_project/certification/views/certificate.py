# coding=utf-8

import base64
import datetime
import os
import re
import uuid
import zipfile
from decimal import Decimal
from io import BytesIO

import djstripe.models
import djstripe.settings
import stripe
from base.models.project import Project
from braces.views import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView
from djstripe import settings as djstripe_settings
from djstripe.enums import PaymentIntentStatus
from djstripe.models import Customer, PaymentIntent
from helpers.notification import send_notification
from PIL import Image
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen import canvas

from ..forms import CertificateForm
from ..mixins import CourseEditPermissionMixin, user_can_manage_organisation
from ..models import (
    Attendee,
    Certificate,
    CertificateType,
    CertifyingOrganisation,
    Course,
    CourseAttendee,
    CourseConvener,
    CourseType,
    TrainingCenter,
)

stripe.api_key = djstripe_settings.STRIPE_SECRET_KEY
NOTICE_TOP_UP_SUCCESS = "top_up_success"


class CertificateMixin(object):
    """Mixin class to provide standard settings for Certificate."""

    model = Certificate
    form_class = CertificateForm


class CertificateCreateView(
    LoginRequiredMixin, CourseEditPermissionMixin, CertificateMixin, CreateView
):
    """Create view for Certificate.

    Each success mints a genuine, publicly verifiable QGIS certificate and
    spends the organisation's purchased credits, so it needs the same
    permission check as the rest of the course views.
    generate_all_certificate already checked both permission and balance;
    this single-certificate path checked neither.
    """

    context_object_name = "certificate"
    template_name = "certificate/create.html"

    def get_success_url(self):
        """Define the redirect URL.

         After successful creation of the object, the User will be redirected
         to the Course detail page.

        :returns: URL
        :rtype: HttpResponse
        """

        return reverse(
            "course-detail",
            kwargs={
                "organisation_slug": self.organisation_slug,
                "slug": self.course_slug,
            },
        )

    def get_context_data(self, **kwargs):
        """Get the context data which is passed to a template.

        :param kwargs: Any arguments to pass to the superclass.
        :type kwargs: dict

        :returns: Context data which will be passed to the template.
        :rtype: dict
        """

        context = super(CertificateCreateView, self).get_context_data(**kwargs)
        context["course"] = self.course
        context["attendee"] = self.attendee
        context["certificate_type"] = self.certificate_type
        return context

    def get_form_kwargs(self):
        """Get keyword arguments from form.

        :returns keyword argument from the form
        :rtype: dict
        """

        # organisation_slug and certifying_organisation are set by
        # CourseEditPermissionMixin.dispatch(). The course and attendee are
        # resolved within that organisation rather than by identifier alone,
        # so that rights over one organisation cannot be used to issue a
        # certificate against another one's course or attendee.
        kwargs = super(CertificateCreateView, self).get_form_kwargs()
        self.project_slug = "qgis"
        self.course_slug = self.kwargs.get("course_slug", None)
        self.certificate_type_pk = self.kwargs.get("certificate_type_pk", None)
        self.pk = self.kwargs.get("pk", None)
        self.course = get_object_or_404(
            Course,
            slug=self.course_slug,
            certifying_organisation=self.certifying_organisation,
        )
        self.attendee = get_object_or_404(
            Attendee, pk=self.pk, certifying_organisation=self.certifying_organisation
        )
        self.certificate_type = get_object_or_404(
            CertificateType, pk=self.certificate_type_pk
        )
        kwargs.update(
            {
                "user": self.request.user,
                "course": self.course,
                "attendee": self.attendee,
                "certificate_type": self.certificate_type,
            }
        )
        return kwargs

    def form_valid(self, form):
        """Save new created certificate

        :param form
        :type form

        :returns HttpResponseRedirect object to success_url
        :rtype: HttpResponseRedirect

        We check that there is no referential integrity error when saving."""

        # The balance itself is enforced by CertificateForm.clean(), which
        # refuses the form outright when there are not enough credits, so by
        # the time we get here the subtraction cannot go negative.
        organisation = self.certifying_organisation

        try:
            super(CertificateCreateView, self).form_valid(form)

            # Update organisation credits every time a certificate is issued.
            cost = organisation.project.certificate_credit
            organisation.organisation_credits -= cost
            organisation.save()

            return HttpResponseRedirect(self.get_success_url())
        except IntegrityError:
            return ValidationError("ERROR: Certificate already exists!")


class CertificateDetailView(DetailView):
    """Detail view for Certificate."""

    model = Certificate
    context_object_name = "certificate"
    template_name = "certificate/detail.html"

    def get_context_data(self, **kwargs):
        """Get the context data which is passed to a template.

        :param kwargs: Any arguments to pass to the superclass.
        :type kwargs: dict

        :returns: Context data which will be passed to the template.
        :rtype: dict
        """

        self.project_slug = "qgis"
        context = super(CertificateDetailView, self).get_context_data(**kwargs)
        certificate = self.object
        if certificate:
            context["certificate"] = certificate
            convener = certificate.course.course_convener
            convener_name = f"{convener.user.first_name} {convener.user.last_name}"

            if convener.title:
                convener_name = f"{convener.title} {convener_name}"

            if convener.degree:
                convener_name = f"{convener_name}, {convener.degree}"

            context["convener_name"] = convener_name
        context["project_slug"] = self.project_slug
        if self.project_slug:
            context["the_project"] = Project.objects.get(slug=self.project_slug)
            context["project"] = context["the_project"]
        return context

    def get_queryset(self):
        """Get the queryset for this view.

        :returns: Queryset which is all certificate in the
            corresponding organisation.
        :rtype: QuerySet
        """

        qs = Certificate.objects.all()
        return qs

    def get_object(self, queryset=None):
        """Get the object for this view.

        :param queryset: A query set
        :type queryset: QuerySet

        :returns: Queryset which is filtered to only show a certificate
            depends on the input certificate ID.
        :rtype: QuerySet
        :raises: Http404
        """

        if queryset is None:
            queryset = self.get_queryset()
        certificate_id = (self.kwargs.get("id") or "").strip()
        if not certificate_id:
            raise Http404("Sorry! Certificate by this ID is not exist.")
        return find_public_certificate(queryset, certificate_id)


def find_public_certificate(queryset, certificate_id: str):
    """Find a certificate by the key used in its public link.

    New certificates are only found by their uuid, which is printed on
    them as the verification code. The sequential certificateID still
    works for paid certificates issued before uuid links existed, because
    those IDs are already printed and emailed.

    :param queryset: Certificates to search in.
    :type queryset: QuerySet

    :param certificate_id: A uuid, or a legacy certificate ID.
    :type certificate_id: str

    :returns: The matching certificate, or None.
    :rtype: Certificate | None
    """

    try:
        key = uuid.UUID(certificate_id)
    except ValueError:
        return queryset.filter(
            certificateID=certificate_id, uuid__isnull=True, is_paid=True
        ).first()
    return queryset.filter(uuid=key).first()


def draw_verification_qr_code(
    page: canvas.Canvas, link: str, x: float, y: float, size: float
) -> None:
    """Draw a QR code of the verification link, with the QGIS sign in the middle.

    The code uses the highest error correction level, so it still scans
    with the sign covering its centre. It sits on a white square, so it
    also scans on a coloured certificate template.

    :param page: The certificate page to draw on.
    :type page: canvas.Canvas

    :param link: The verification link the QR code opens.
    :type link: str

    :param x: Left edge of the QR code, in points.
    :type x: float

    :param y: Bottom edge of the QR code, in points.
    :type y: float

    :param size: Width and height of the QR code, in points.
    :type size: float
    """

    qr_code = QrCodeWidget(link, barLevel="H")
    left, bottom, right, top = qr_code.getBounds()
    drawing = Drawing(
        size,
        size,
        transform=[size / (right - left), 0, 0, size / (top - bottom), 0, 0],
    )
    drawing.add(qr_code)

    page.saveState()
    page.setFillColorRGB(1, 1, 1)
    page.rect(x, y, size, size, stroke=0, fill=1)
    renderPDF.draw(drawing, page, x, y)

    logo = finders.find("images/qgis-sign.png")
    if logo:
        backdrop_size = size * 0.26
        logo_size = size * 0.2
        page.rect(
            x + (size - backdrop_size) / 2,
            y + (size - backdrop_size) / 2,
            backdrop_size,
            backdrop_size,
            stroke=0,
            fill=1,
        )
        page.drawImage(
            logo,
            x + (size - logo_size) / 2,
            y + (size - logo_size) / 2,
            width=logo_size,
            height=logo_size,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
    page.restoreState()


def generate_pdf(
    pathname,
    project,
    course,
    attendee,
    certificate,
    current_site,
    wording="Has attended and completed the course:",
):
    """Create the PDF object, using the response object as its file."""

    # Check if certificate is paid or not
    # Allow dummy certificate (preview) to be generated
    if not isinstance(certificate, DummyCertificate) and not certificate.is_paid:
        return
    # Register new font
    try:
        font_folder = os.path.join(settings.STATIC_ROOT, "fonts/times-new-roman")
        bold_ttf_file = os.path.join(font_folder, "Times New Roman Gras 700.ttf")
        regular_ttf_file = os.path.join(font_folder, "Times New Roman 400.ttf")
        pdfmetrics.registerFont(TTFont("Noto-Bold", bold_ttf_file))
        pdfmetrics.registerFont(TTFont("Noto-Regular", regular_ttf_file))
    except (TTFError, KeyError):
        pass

    page = canvas.Canvas(pathname, pagesize=landscape(A4))
    width, height = A4
    center = height * 0.5
    convener = course.course_convener
    convener_name = f"{convener.user.first_name} {convener.user.last_name}"

    if convener.title:
        convener_name = f"{convener.title} {convener_name}"

    if convener.degree:
        convener_name = f"{convener_name}, {convener.degree}"

    start = course.start_date
    end = course.end_date
    course_duration = (
        f"From {start.day} {start:%B} {start.year} to {end.day} {end:%B} {end.year}"
    )

    if course.course_type.instruction_hours:
        course_duration = (
            f"{course_duration} "
            f"({course.course_type.instruction_hours} hours of instruction)"
        )

    if project.image_file:
        if hasattr(project.image_file, "open"):
            project.image_file.open()
        project_logo = ImageReader(project.image_file)
    else:
        project_logo = None

    if course.certifying_organisation.logo:
        if hasattr(course.certifying_organisation.logo, "open"):
            course.certifying_organisation.logo.open()
        organisation_logo = ImageReader(course.certifying_organisation.logo)
    else:
        organisation_logo = None

    if project.project_representative_signature:
        if hasattr(project.project_representative_signature, "open"):
            project.project_representative_signature.open()
        project_representative_signature = ImageReader(
            project.project_representative_signature
        )
    else:
        project_representative_signature = None

    if course.course_convener.signature:
        if hasattr(course.course_convener.signature, "open"):
            course.course_convener.signature.open()
        convener_signature = ImageReader(course.course_convener.signature)
    else:
        convener_signature = None

    if course.template_certificate:
        if hasattr(course.template_certificate, "open"):
            course.template_certificate.open()
        background = ImageReader(course.template_certificate)
    else:
        background = None

    # Certificate margin.
    margin_right = height - 50
    margin_left = 50
    margin_bottom = 50
    max_left = margin_right - 100

    # Draw things on the PDF. Here's where the PDF generation happens.
    # See the ReportLab documentation for the full list of functionality.
    if background is not None:
        page.drawImage(
            background,
            0,
            0,
            height=width,
            width=height,
            preserveAspectRatio=True,
            mask="auto",
        )
    page.setFillColorRGB(0.1, 0.1, 0.1)
    page.setFont("Noto-Regular", 18)

    if project_logo is not None:
        page.drawImage(
            project_logo,
            50,
            450,
            width=100,
            height=100,
            preserveAspectRatio=True,
            mask="auto",
        )

    if organisation_logo is not None:
        page.drawImage(
            organisation_logo,
            max_left,
            450,
            height=100,
            width=100,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )

    page.setFont("Noto-Bold", 26)
    page.drawCentredString(center, 480, "Certificate of Completion")

    page.setFont("Noto-Bold", 26)

    page.drawCentredString(
        center,
        400,
        f"{attendee.firstname} {attendee.surname or ''}",
    )
    page.setFont("Noto-Regular", 16)
    page.drawCentredString(center, 370, wording)
    page.setFont("Noto-Bold", 20)
    page.drawCentredString(center, 335, course.course_type.name)
    page.setFont("Noto-Regular", 16)
    page.drawCentredString(center, 300, "With a trained competence in:")
    page.setFont("Noto-Bold", 14)
    page.drawCentredString(center, 280, f"{course.trained_competence[:120]}")
    page.setFont("Noto-Regular", 16)
    page.drawCentredString(center, 250, course_duration)

    page.setFillColorRGB(0.1, 0.1, 0.1)
    page.drawCentredString(
        center,
        220,
        f"Convened by {convener_name} at {course.training_center}",
    )

    if project_representative_signature is not None:
        page.drawImage(
            project_representative_signature,
            (margin_left + 100),
            (margin_bottom + 70),
            width=100,
            height=70,
            preserveAspectRatio=True,
            anchor="s",
            mask="auto",
        )

    if convener_signature is not None:
        page.drawImage(
            convener_signature,
            (margin_right - 200),
            (margin_bottom + 70),
            width=100,
            height=70,
            preserveAspectRatio=True,
            anchor="s",
            mask="auto",
        )

    page.setFont("Noto-Regular", 12)
    if project.project_representative:
        representative = project.project_representative
        page.drawCentredString(
            (margin_left + 150),
            (margin_bottom + 60),
            f"{representative.first_name} {representative.last_name}",
        )
    page.drawCentredString((margin_right - 150), (margin_bottom + 60), convener_name)
    page.line(
        (margin_left + 70),
        (margin_bottom + 55),
        (margin_left + 230),
        (margin_bottom + 55),
    )
    page.line(
        (margin_right - 70),
        (margin_bottom + 55),
        (margin_right - 230),
        (margin_bottom + 55),
    )
    page.setFont("Noto-Regular", 13)
    page.drawCentredString(
        (margin_left + 150), (margin_bottom + 40), "Project Representative"
    )
    page.drawCentredString(
        (margin_right - 150), (margin_bottom + 40), "Course Convener"
    )

    # Footnotes.
    verification_link = (
        f"https://{current_site}/en/certificate/{certificate.public_id}/"
    )
    if certificate.legacy_link:
        page.setFont("Noto-Regular", 14)
        page.drawString(
            margin_left, margin_bottom - 10, f"ID: {certificate.public_id}"
        )
    else:
        qr_code_size = 100
        draw_verification_qr_code(
            page,
            verification_link,
            center - qr_code_size / 2,
            margin_bottom + 40,
            qr_code_size,
        )
    page.setFont("Noto-Regular", 8)
    page.drawString(
        margin_left,
        (margin_bottom - 20),
        f"You can verify this certificate by scanning the QR Code or visiting {verification_link}.",
    )

    # Close the PDF object cleanly.
    page.showPage()
    page.save()


def certificate_pdf_path(certificate, project) -> str:
    """Where the rendered PDF of a certificate is stored.

    :param certificate: The certificate.
    :type certificate: Certificate

    :param project: The project the certificate belongs to.
    :type project: Project

    :returns: Absolute path of the PDF file.
    :rtype: str
    """

    project_folder = (project.name.lower()).replace(" ", "_")
    return os.path.join(
        "/home/web/media", "pdf", project_folder, certificate.pdf_filename
    )


def serve_certificate_pdf(certificate, project, current_site: str) -> FileResponse:
    """Return the PDF of a certificate, rendering it first if needed.

    :param certificate: The certificate to serve.
    :type certificate: Certificate

    :param project: The project the certificate belongs to.
    :type project: Project

    :param current_site: Host name printed in the verification link.
    :type current_site: str

    :returns: The PDF file.
    :rtype: FileResponse
    :raises: Http404 when no PDF can be produced (e.g. unpaid certificate).
    """

    pathname = certificate_pdf_path(certificate, project)
    if not os.path.exists(pathname):
        os.makedirs(os.path.dirname(pathname), exist_ok=True)
        certificate_type = (
            certificate.certificate_type or certificate.course.certificate_type
        )
        generate_pdf(
            pathname,
            project,
            certificate.course,
            certificate.attendee,
            certificate,
            current_site,
            certificate_type.wording,
        )
    try:
        return FileResponse(open(pathname, "rb"), content_type="application/pdf")
    except FileNotFoundError:
        raise Http404()


def certificate_pdf_view(request, **kwargs):
    """Serve a certificate PDF by course and attendee.

    Course slugs are public and attendee pks are sequential, so this link
    can be guessed. It stays public only for legacy certificates, whose
    link was already emailed. For newer ones it is limited to people who
    manage the organisation; attendees get the uuid link instead.
    """

    project_slug = "qgis"
    course_slug = kwargs.pop("course_slug")
    pk = kwargs.pop("pk")
    project = get_object_or_404(Project, slug=project_slug)
    course = get_object_or_404(Course, slug=course_slug)
    certificate = get_object_or_404(Certificate, course=course, attendee__pk=pk)

    if not certificate.legacy_link and not user_can_manage_organisation(
        request.user, course.certifying_organisation
    ):
        raise Http404()

    return serve_certificate_pdf(certificate, project, request.META["HTTP_HOST"])


def certificate_uuid_pdf_view(request, **kwargs):
    """Serve a certificate PDF by its uuid. This is the public PDF link."""

    certificate = get_object_or_404(Certificate, uuid=kwargs["uuid"])
    project = get_object_or_404(Project, slug="qgis")
    return serve_certificate_pdf(certificate, project, request.META["HTTP_HOST"])


@login_required
def download_certificates_zip(request: HttpRequest, **kwargs: object) -> HttpResponse:
    """Download all certificates in a course as one zip file.

    A single certificate is meant to be publicly verifiable by its ID, but
    handing out a whole cohort is a different thing: organisation and course
    slugs are listed on public pages, so with no check at all this turned a
    per-certificate verification feature into a bulk export of every
    attendee's name and course history across the whole site.

    :param request: The incoming request.
    :type request: HttpRequest

    :returns: A zip file of the paid certificates for this course.
    :rtype: HttpResponse
    """

    project_slug = "qgis"
    course_slug = kwargs.pop("course_slug")
    organisation_slug = kwargs.pop("organisation_slug")
    organisation = get_object_or_404(CertifyingOrganisation, slug=organisation_slug)

    if not user_can_manage_organisation(request.user, organisation):
        raise PermissionDenied(
            _("You do not have permission to download these certificates.")
        )

    course = get_object_or_404(
        Course, slug=course_slug, certifying_organisation=organisation
    )

    certificates = Certificate.objects.filter(course=course)

    filenames = []
    for certificate in certificates:
        if not certificate.is_paid:
            continue
        pdf_file = certificate_pdf_view(
            request,
            pk=certificate.attendee.pk,
            project_slug=project_slug,
            course_slug=course_slug,
            organisation_slug=organisation_slug,
        )

        with open(f"/tmp/{certificate.certificateID}.pdf", "wb") as pdf:
            pdf.write(pdf_file.getvalue())

        filenames.append(f"/tmp/{certificate.certificateID}.pdf")

    zip_subdir = f"{course.name}"

    in_memory_data = BytesIO()
    zf = zipfile.ZipFile(in_memory_data, "w")

    for fpath in filenames:
        fdir, fname = os.path.split(fpath)
        zip_path = os.path.join(zip_subdir, fname)

        zf.write(fpath, zip_path)

    zf.close()

    response = HttpResponse(
        in_memory_data.getvalue(), content_type="application/x-zip-compressed"
    )
    response["Content-Disposition"] = "attachment; filename=certificates.zip"

    return response


@login_required
def update_paid_status(request: HttpRequest, **kwargs: object) -> HttpResponse:
    """View to update the is_paid status of certificate in a course.

    Marking a certificate paid spends the organisation's credits, which are
    bought with real money, so the caller has to be someone entitled to
    manage that organisation. The course and attendee are looked up within
    the organisation named in the URL rather than by slug and pk alone -
    otherwise a user who legitimately manages organisation A could act on
    organisation B's course by pairing the two identifiers.

    :param request: HTTP request object
    :type request: HttpRequest

    :param kwargs: Keyword arguments from the URL
    :type kwargs: dict

    :returns: The confirmation page, or a redirect to the course detail page.
    :rtype: HttpResponse
    """

    project_slug = "qgis"
    organisation_slug = kwargs.pop("organisation_slug")
    course_slug = kwargs.pop("course_slug")
    attendee_pk = kwargs.pop("pk")
    organisation = get_object_or_404(CertifyingOrganisation, slug=organisation_slug)

    if not user_can_manage_organisation(request.user, organisation):
        raise PermissionDenied(
            _("You do not have permission to modify this organisation.")
        )

    course = get_object_or_404(
        Course, slug=course_slug, certifying_organisation=organisation
    )
    attendee = get_object_or_404(
        Attendee, pk=attendee_pk, certifying_organisation=organisation
    )
    project = get_object_or_404(Project, slug=project_slug)
    url = reverse(
        "course-detail",
        kwargs={"organisation_slug": organisation_slug, "slug": course_slug},
    )

    if request.method == "POST":
        remaining_credits = (
            organisation.organisation_credits or 0
        ) - project.certificate_credit
        if remaining_credits < 0:
            return HttpResponseForbidden(
                _("You do not have enough credits to pay for this " "certificate.")
            )

        for certificate in Certificate.objects.filter(course=course, attendee=attendee):
            certificate.is_paid = True
            certificate.save()
        organisation.organisation_credits = remaining_credits
        organisation.save()
        return HttpResponseRedirect(url)

    return render(
        request,
        "certificate/update_is_paid.html",
        context={
            "course": course,
            "project_slug": project_slug,
            "organisation_slug": organisation_slug,
            "course_slug": course_slug,
            "attendee": attendee,
            "project": project,
        },
    )


def top_up_unavailable(request, **kwargs):
    project_slug = "qgis"
    project = Project.objects.get(slug=project_slug)
    organisation = CertifyingOrganisation.objects.filter(approved=False)
    has_pending = False
    if organisation:
        has_pending = True

    return render(
        request,
        "certificate/top_up_unavailable.html",
        context={"the_project": project, "has_pending_organisations": has_pending},
    )


def email_all_attendees(request, **kwargs):
    """Send email to all attendees in a course."""

    project_slug = "qgis"
    course_slug = kwargs.get("course_slug", None)
    organisation_slug = kwargs.get("organisation_slug", None)
    project = Project.objects.get(slug=project_slug)
    course = Course.objects.get(slug=course_slug)
    certificates = Certificate.objects.filter(
        is_paid=True, course=course
    ).select_related("attendee")
    attendee_list_object = [certificate.attendee for certificate in certificates]

    organisation = CertifyingOrganisation.objects.filter(approved=False)
    has_pending = False
    if organisation:
        has_pending = True

    url = reverse(
        "course-detail",
        kwargs={"organisation_slug": organisation_slug, "slug": course_slug},
    )

    if request.method == "POST":

        site = request.get_host()
        for certificate in certificates:
            attendee = certificate.attendee
            # Send email to each attendee with the link to their certificate.
            if certificate.legacy_link:
                pdf_url = (
                    f"https://{site}/en/{project.slug}/certifyingorganisation/"
                    f"{course.certifying_organisation.slug}/course/{course.slug}/"
                    f"print/{attendee.pk}/"
                )
            else:
                pdf_path = reverse("certificate-pdf", kwargs={"uuid": certificate.uuid})
                pdf_url = f"https://{site}{pdf_path}"
            lastname = attendee.surname if attendee.surname else ""
            convener = course.course_convener.user

            send_mail(
                f"Certificate from {course.course_type} Course",
                f"Dear {attendee.firstname} {lastname},\n\n"
                "Congratulations!\n"
                "Your certificate from the following course "
                "has been issued.\n\n"
                f"Course type: {course.course_type}\n"
                f"Course date: {course.start_date:%d %B %Y} "
                f"to {course.end_date:%d %B %Y}\n"
                f"Training center: {course.training_center}\n"
                f"Certifying organisation: {course.certifying_organisation.name}\n\n"
                "You may print the certificate "
                "by visiting:\n"
                f"{pdf_url}\n\n"
                f"Sincerely,\n{convener.first_name} {convener.last_name}",
                settings.DEFAULT_FROM_EMAIL,
                [attendee.email],
                fail_silently=False,
            )

        messages.success(request, "Email sent", "email_sent")
        return HttpResponseRedirect(url)

    return render(
        request,
        "certificate/send_email_confirm.html",
        context={
            "the_project": project,
            "has_pending_organisations": has_pending,
            "attendees": attendee_list_object,
        },
    )


def regenerate_certificate(request, **kwargs):
    """Regenerate a pdf certificate for an attendee."""

    project_slug = "qgis"
    organisation_slug = kwargs.pop("organisation_slug", None)
    course_slug = kwargs.pop("course_slug", None)
    pk = kwargs.pop("pk")
    project = Project.objects.get(slug=project_slug)
    certifying_organisation = get_object_or_404(
        CertifyingOrganisation, slug=organisation_slug
    )
    course = get_object_or_404(
        Course, slug=course_slug, certifying_organisation=certifying_organisation
    )
    attendee = get_object_or_404(
        Attendee, pk=pk, certifying_organisation=certifying_organisation
    )
    certificate = get_object_or_404(Certificate, course=course, attendee=attendee)

    # Checking user permissions.
    if (
        request.user.is_staff
        or request.user == project.owner
        or request.user in project.certification_managers.all()
        or request.user in certifying_organisation.organisation_owners.all()
        or request.user == project.project_representative
    ):
        pass
    else:
        raise Http404

    pending_organisation = CertifyingOrganisation.objects.filter(approved=False)
    has_pending = False
    if pending_organisation:
        has_pending = True

    pathname = certificate_pdf_path(certificate, project)
    found = os.path.exists(pathname)

    if request.method == "POST":
        if found:
            # Delete existing certificate
            os.remove(pathname)

        makepath = os.path.dirname(pathname)
        if not os.path.exists(makepath):
            os.makedirs(makepath)

        current_site = request.META["HTTP_HOST"]
        certificate_type = course.certificate_type

        if certificate.certificate_type:
            certificate_type = certificate.certificate_type
        generate_pdf(
            pathname,
            project,
            course,
            attendee,
            certificate,
            current_site,
            certificate_type.wording,
        )
        try:
            return FileResponse(open(pathname, "rb"), content_type="application/pdf")
        except FileNotFoundError:
            raise Http404()

    return render(
        request,
        "certificate/regenerate_certificate.html",
        context={
            "the_project": project,
            "has_pending_organisations": has_pending,
            "attendee": attendee,
            "id": certificate.certificateID,
            "certificate_type": certificate.certificate_type,
            "course": course,
        },
    )


def generate_all_certificate(request, **kwargs):
    """Generate all certificates within a course."""

    project_slug = "qgis"
    course_slug = kwargs.pop("course_slug", None)
    organisation_slug = kwargs.get("organisation_slug", None)
    course = Course.objects.get(slug=course_slug)
    project = Project.objects.get(slug=project_slug)
    certifying_organisation = CertifyingOrganisation.objects.get(slug=organisation_slug)

    if (
        not certifying_organisation.organisation_credits
        or certifying_organisation.organisation_credits <= 0
    ):
        return HttpResponseForbidden(
            "You do not have enough credits to generate certificates"
        )
    # Checking user permissions.
    if (
        request.user.is_staff
        or request.user == project.owner
        or request.user in project.certification_managers.all()
        or request.user in certifying_organisation.organisation_owners.all()
        or request.user == project.project_representative
    ):
        pass
    else:
        raise Http404

    course_attendees = CourseAttendee.objects.filter(course=course)
    if request.method == "POST":
        for course_attendee in course_attendees:

            try:
                certificate = Certificate.objects.get(
                    author=request.user,
                    attendee=course_attendee.attendee,
                    course=course,
                )
            except Certificate.DoesNotExist:

                remaining_credits = (
                    certifying_organisation.organisation_credits
                    - certifying_organisation.project.certificate_credit
                )

                is_paid = False
                if remaining_credits >= 0:
                    is_paid = True

                certificate = Certificate.objects.create(
                    author=request.user,
                    attendee=course_attendee.attendee,
                    course=course,
                    is_paid=is_paid,
                )

                if certificate and (remaining_credits >= 0):
                    certifying_organisation.organisation_credits = remaining_credits
                    certifying_organisation.save()

        url = reverse(
            "course-detail",
            kwargs={"organisation_slug": organisation_slug, "slug": course_slug},
        )

        messages.success(request, "All certificates are generated", "generate")
        return HttpResponseRedirect(url)
    return render(
        request,
        "certificate/generate_all_certificate.html",
        context={
            "course": course,
            "attendees": course_attendees,
        },
    )


def regenerate_all_certificate(request, **kwargs):
    """Regenerate all certificates within a course."""

    project_slug = "qgis"
    course_slug = kwargs.pop("course_slug", None)
    organisation_slug = kwargs.get("organisation_slug", None)
    course = Course.objects.get(slug=course_slug)
    project = Project.objects.get(slug=project_slug)
    certifying_organisation = CertifyingOrganisation.objects.get(slug=organisation_slug)

    # Checking user permissions.
    if (
        request.user.is_staff
        or request.user == project.owner
        or request.user in project.certification_managers.all()
        or request.user in certifying_organisation.organisation_owners.all()
        or request.user == project.project_representative
    ):
        pass
    else:
        raise Http404

    attendees_pk = Certificate.objects.filter(course=course).values_list(
        "attendee", flat=True
    )

    attendees = []
    for pk in attendees_pk:
        attendees.append(Attendee.objects.get(pk=pk))

    pending_organisation = CertifyingOrganisation.objects.filter(approved=False)
    has_pending = False
    if pending_organisation:
        has_pending = True

    url = reverse(
        "course-detail",
        kwargs={"organisation_slug": organisation_slug, "slug": course_slug},
    )

    # Attendee and her certificate
    certificates_dict = {}
    for attendee in attendees:
        certificates_dict[attendee] = Certificate.objects.get(
            course=course, attendee=attendee
        )

    if request.method == "POST":

        # Delete all existing certificate in a course.
        for key, value in certificates_dict.items():
            pathname = certificate_pdf_path(value, project)
            found = os.path.exists(pathname)
            if found:
                os.remove(pathname)

        # Generate all certificates in a course
        current_site = request.META["HTTP_HOST"]
        project_folder = (project.name.lower()).replace(" ", "_")
        makepath = "/home/web/media/pdf/{}/".format(project_folder)
        if not os.path.exists(makepath):
            os.makedirs(makepath)

        for key, value in certificates_dict.items():
            pathname = certificate_pdf_path(value, project)
            certificate_type = course.certificate_type
            if value.certificate_type:
                certificate_type = value.certificate_type
            generate_pdf(
                pathname,
                project,
                course,
                key,
                value,
                current_site,
                certificate_type.wording,
            )

        messages.success(request, "All certificates are updated", "regenerate")
        return HttpResponseRedirect(url)

    return render(
        request,
        "certificate/regenerate_all_certificate.html",
        context={
            "the_project": project,
            "has_pending_organisations": has_pending,
            "certificates": certificates_dict,
            "course": course,
        },
    )


class DummyAttendee(object):
    """Dummy object for preview certificate."""

    def __init__(self):
        self.firstname = "Jane"
        self.surname = "Doe"


class DummyCourse(object):
    """Dummy object for preview certificate."""

    def __init__(
        self,
        course_convener,
        course_type,
        training_center,
        start_date,
        end_date,
        certifying_organisation,
        template_certificate,
        trained_competence,
    ):
        self.course_convener = course_convener
        self.course_type = course_type
        self.training_center = training_center
        self.start_date = start_date
        self.end_date = end_date
        self.certifying_organisation = certifying_organisation
        self.template_certificate = template_certificate
        self.trained_competence = trained_competence


class DummyCertificate(object):
    """Dummy object for preview certificate."""

    def __init__(self, course, attendee, project):
        self.certificateID = f"{project.name}-DEMO"
        self.public_id = "00000000-0000-0000-0000-000000000000"
        self.legacy_link = False
        self.course = course
        self.attendee = attendee


def preview_certificate(request, **kwargs):
    """Generate pdf for preview upon creating new course."""
    # Register new font
    try:
        font_folder = os.path.join(settings.STATIC_ROOT, "fonts/times-new-roman")
        bold_ttf_file = os.path.join(font_folder, "Times New Roman Gras 700.ttf")
        regular_ttf_file = os.path.join(font_folder, "Times New Roman 400.ttf")
        pdfmetrics.registerFont(TTFont("Noto-Bold", bold_ttf_file))
        pdfmetrics.registerFont(TTFont("Noto-Regular", regular_ttf_file))
    except (TTFError, KeyError):
        pass

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'filename="preview.pdf"'

    project_slug = "qgis"
    project = Project.objects.get(slug=project_slug)
    organisation_slug = kwargs.pop("organisation_slug")

    convener_id = request.POST.get("course_convener", None)
    certificate_type_id = request.POST.get("certificate_type", None)
    if convener_id is not None:
        # Get all posted data.
        course_convener = CourseConvener.objects.get(id=convener_id)
        training_center_id = request.POST.get("training_center", None)
        training_center = TrainingCenter.objects.get(id=training_center_id)
        course_type_id = request.POST.get("course_type", None)
        course_type = CourseType.objects.get(id=course_type_id)
        start_date = request.POST.get("start_date", None)
        course_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_date = request.POST.get("end_date", None)
        course_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        certifying_organisation = CertifyingOrganisation.objects.get(
            slug=organisation_slug
        )
        raw_image = request.POST.get("template_certificate", None)
        trained_competence = request.POST.get("trained_competence", "")
        if "base64" in raw_image:
            image_data = re.sub("^data:image/.+;base64,", "", raw_image)
            decoded_image = base64.b64decode(image_data.encode("utf-8"))
            template_certificate = Image.open(BytesIO(decoded_image))
        else:
            template_certificate = None

        # Create dummy objects
        attendee = DummyAttendee()
        course = DummyCourse(
            course_convener,
            course_type,
            training_center,
            course_start_date,
            course_end_date,
            certifying_organisation,
            template_certificate,
            trained_competence,
        )
        certificate = DummyCertificate(course, attendee, project)

        current_site = request.META["HTTP_HOST"]

        if certificate_type_id:
            try:
                certificate_type = CertificateType.objects.get(id=certificate_type_id)
                generate_pdf(
                    response,
                    project,
                    course,
                    attendee,
                    certificate,
                    current_site,
                    certificate_type.wording,
                )
            except CertificateType.DoesNotExist:
                generate_pdf(
                    response, project, course, attendee, certificate, current_site
                )
        else:
            generate_pdf(response, project, course, attendee, certificate, current_site)

    else:
        # When preview page is refreshed, the data is gone so user needs to
        # go back to create page.

        page = canvas.Canvas(response, pagesize=landscape(A4))
        width, height = A4
        center = height * 0.5
        page.setFillColorRGB(0.1, 0.1, 0.1)
        page.setFont("Noto-Bold", 26)
        page.drawCentredString(center, 480, "Certificate of Completion")
        page.setFont("Noto-Regular", 16)
        page.drawCentredString(
            center,
            360,
            "To preview your certificate template, "
            "please go to create new course page",
        )
        page.drawCentredString(center, 335, "and click on Preview Certificate button.")
        page.showPage()
        page.save()

    return response


class TopUpView(TemplateView):
    template_name = "certificate/top_up.html"
    project_slug = ""
    organisation_slug = ""

    def get_context_data(self, **kwargs):
        context = super(TopUpView, self).get_context_data(**kwargs)
        self.project_slug = "qgis"
        self.organisation_slug = self.kwargs.get("organisation_slug", None)

        certifying_organisation = CertifyingOrganisation.objects.get(
            slug=self.organisation_slug
        )
        project = Project.objects.get(slug=self.project_slug)

        context["the_project"] = project
        context["cert_organisation"] = certifying_organisation

        return context

    def process_charge(
        self,
        stripe_source_id,
        cost_of_credits,
        currency,
        statement_descriptor="",
        description="",
        metadata=None,
    ):
        """
        Creates a charge for user.

        :param stripe_source_id: Id from stripe source
        :param cost_of_credits: cost of the total credits
        :param currency: currency of the cost
        :param metadata: A set of key/value pairs useful for storing
            additional information.
        :param statement_descriptor: An arbitrary string to be displayed on the
            customer's credit card statement.
        :param description: Description of the payment
        :return: paid, outcome
        """
        # Create the stripe Customer, by default subscriber Model is User,
        # this can be overridden with settings.DJSTRIPE_SUBSCRIBER_MODEL
        if metadata is None:
            metadata = {}
        customer, created = djstripe.models.Customer.get_or_create(
            subscriber=self.request.user
        )

        customer.add_card(stripe_source_id)

        charge = customer.charge(
            amount=cost_of_credits,
            currency=currency,
            description=description,
            metadata=metadata,
            statement_descriptor=statement_descriptor,
        )
        return charge.paid, charge.outcome

    def post(self, request, *args, **kwargs):
        """Post the project_slug from the URL and define the Project

        :param request: HTTP request object
        :type request: HttpRequest

        :param args: Positional arguments
        :type args: tuple

        :param kwargs: Keyword arguments
        :type kwargs: dict

        :returns: Unaltered request object
        :rtype: HttpResponse
        """
        total_credits = self.request.POST.get("total-credits", None)
        stripe_source_id = self.request.POST.get("stripe-source-id", None)

        self.project_slug = "qgis"
        self.organisation_slug = self.kwargs.get("organisation_slug", None)

        project = Project.objects.get(slug=self.project_slug)

        organisation = CertifyingOrganisation.objects.get(slug=self.organisation_slug)

        if not total_credits or not stripe_source_id:
            raise Http404("Missing important value")

        try:
            total_credits_decimal = Decimal(total_credits)
            total_credits = int(total_credits)
        except ValueError:
            raise Http404("Wrong total credits format")

        cost_of_credits = project.credit_cost * total_credits_decimal
        plural = "s" if total_credits > 1 else ""
        description = f"Top up {total_credits} credit{plural}"
        charged, outcome = self.process_charge(
            stripe_source_id=stripe_source_id,
            cost_of_credits=cost_of_credits,
            currency=project.credit_cost_currency,
            metadata={
                "name": "Top up credits",
                "organisation": organisation,
                "organisation_id": organisation.id,
                "project": project,
                "project_id": project.id,
                "user_id": self.request.user.id,
                "added_credit": total_credits,
                "credit_cost": project.credit_cost,
                "total_payment": cost_of_credits,
                "currency": project.credit_cost_currency,
            },
            description=description,
            statement_descriptor=description,
        )

        if charged:
            organisation.organisation_credits += total_credits
            organisation.save()
            organisation_owners = organisation.organisation_owners.all()
            send_notification(
                users=[self.request.user] + list(organisation_owners),
                label=NOTICE_TOP_UP_SUCCESS,
                extra_context={
                    "author": self.request.user,
                    "top_up_credits": total_credits,
                    "currency": project.get_credit_cost_currency_display(),
                    "payment_amount": cost_of_credits,
                    "certifying_organisation": organisation,
                    "total_credits": organisation.organisation_credits,
                },
                request_user=self.request.user,
            )
            messages.success(
                request,
                f"Your purchase of <b>{total_credits}</b> credits "
                "has been successful",
                "credits_top_up",
            )

        return HttpResponseRedirect(
            reverse(
                "certifyingorganisation-detail", kwargs={"slug": self.organisation_slug}
            )
        )


class CertificateRevokeView(LoginRequiredMixin, DeleteView):
    """Revoke view for Certificate."""

    model = Certificate
    context_object_name = "certificate"
    template_name = "certificate/delete.html"

    def get_object(self, queryset=None):
        """
        Returns the object the view is displaying.

        By default this requires `self.queryset` and a `pk` or `slug` argument
        in the URLconf, but subclasses can override this to return any object.
        """
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()

        # Next, try looking up by primary key.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        slug = self.kwargs.get(self.slug_url_kwarg, None)
        if pk is not None:
            queryset = queryset.filter(attendee__pk=pk)

        # Next, try looking up by slug.
        if slug is not None and (pk is None or self.query_pk_and_slug):
            slug_field = self.get_slug_field()
            queryset = queryset.filter(**{slug_field: slug})

        # If none of those are defined, it's an error.
        if pk is None and slug is None:
            raise AttributeError(
                f"Generic detail view {self.__class__.__name__} must be called "
                "with either an object pk or a slug."
            )

        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get(self, request, *args, **kwargs):
        """Get the course_slug and course attendee pk from the URL
        and define the course.

        :param request: HTTP request object
        :type request: HttpRequest

        :param args: Positional arguments
        :type args: tuple

        :param kwargs: Keyword arguments
        :type kwargs: dict

        :returns: Unaltered request object
        :rtype: HttpResponse
        """

        self.course_slug = self.kwargs.get("course_slug", None)
        self.pk = self.kwargs.get("pk", None)
        self.course = Course.objects.get(slug=self.course_slug)

        return super(CertificateRevokeView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Post the project_slug, organisation_slug, course_slug from the URL.

        :param request: HTTP request object
        :type request: HttpRequest

        :param args: Positional arguments
        :type args: tuple

        :param kwargs: Keyword arguments
        :type kwargs: dict

        :returns: Unaltered request object
        :rtype: HttpResponse
        """

        self.project_slug = "qgis"
        self.organisation_slug = self.kwargs.get("organisation_slug", None)
        self.course_slug = self.kwargs.get("course_slug", None)
        self.course = Course.objects.get(slug=self.course_slug)

        return super(CertificateRevokeView, self).post(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        """Refuse revocation once the certificate's 7 day window has closed.

        This is checked here rather than in get(), so that it covers POST as
        well: enforcing it on GET alone left the window bypassable by posting
        to the URL directly.
        """

        course_slug = self.kwargs.get("course_slug", None)
        try:
            course = Course.objects.get(slug=course_slug)
        except Course.DoesNotExist:
            raise Http404("Sorry! We could not find your course!")

        certificate = Certificate.objects.filter(
            course=course, attendee__pk=self.kwargs.get("pk")
        ).first()

        if certificate and not certificate.is_revocable:
            if certificate.issue_date:
                reason = _(
                    "Certificates can only be revoked within %(days)s days of "
                    "being issued, and this one was issued on %(issued)s."
                ) % {
                    "days": Certificate.REVOCATION_WINDOW_DAYS,
                    "issued": certificate.issue_date,
                }
            else:
                reason = _(
                    "This certificate has no recorded issue date and is kept "
                    "as a permanent record."
                )
            messages.error(
                request,
                _("This certificate can no longer be revoked. %(reason)s")
                % {"reason": reason},
            )
            return HttpResponseRedirect(
                reverse(
                    "course-detail",
                    kwargs={
                        "organisation_slug": self.kwargs.get("organisation_slug"),
                        "slug": course_slug,
                    },
                )
            )

        return super(CertificateRevokeView, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Define the redirect URL.

        After successful deletion  of the object, the User will be redirected
        to the Course detail page.

        :returns: URL
        :rtype: HttpResponse
        """

        return reverse(
            "course-detail",
            kwargs={
                "organisation_slug": self.organisation_slug,
                "slug": self.course_slug,
            },
        )

    def get_queryset(self):
        """Get the queryset for this view.

        :returns: Course Attendee queryset filtered by Course
        :rtype: QuerySet
        :raises: Http404
        """

        if not self.request.user.is_authenticated:
            raise Http404
        qs = Certificate.objects.filter(course=self.course)
        return qs

    def form_valid(self, form):
        """Refund the credit and remove the PDF, then delete the certificate.

        This logic used to live in delete(). Since Django 4.0 DeleteView
        deletes through FormMixin and never calls delete(), so none of it was
        running: revoking a certificate silently failed to refund the
        organisation and left the generated PDF on disk.
        """

        # Update organisation credits every time a certificate is revoked.
        organisation = CertifyingOrganisation.objects.get(slug=self.organisation_slug)
        remaining_credits = (
            organisation.organisation_credits + organisation.project.certificate_credit
        )
        organisation.organisation_credits = remaining_credits
        organisation.save()

        # Remove the rendered certificate so a revoked ID cannot be served.
        certificate = self.object
        pathname = certificate_pdf_path(certificate, organisation.project)
        found = os.path.exists(pathname)
        if found:
            os.remove(pathname)

        return super(CertificateRevokeView, self).form_valid(form)


class CheckoutSessionSuccessView(TemplateView):
    """
    Template View for showing Checkout Payment Success
    """

    template_name = "checkout_success.html"

    def get(self, request, *args, **kwargs):
        session = stripe.checkout.Session.retrieve(self.request.GET.get("session_id"))
        if session["payment_status"] == "paid":
            try:
                payment_intent = PaymentIntent.objects.get(id=session["id"])
                if payment_intent.status == PaymentIntentStatus.requires_payment_method:
                    user = self.request.user

                    organisation = CertifyingOrganisation.objects.get(
                        id=session["metadata"]["organisation_id"]
                    )
                    total_credits = int(session["metadata"]["credits_quantity"])
                    cost_of_credits = payment_intent.amount / 100

                    organisation.organisation_credits += total_credits
                    organisation.save()
                    organisation_owners = organisation.organisation_owners.all()

                    project = organisation.project

                    send_notification(
                        users=[self.request.user] + list(organisation_owners),
                        label=NOTICE_TOP_UP_SUCCESS,
                        extra_context={
                            "author": self.request.user,
                            "top_up_credits": total_credits,
                            "currency": (project.get_credit_cost_currency_display()),
                            "payment_amount": cost_of_credits,
                            "certifying_organisation": organisation,
                            "total_credits": organisation.organisation_credits,
                        },
                        request_user=user,
                    )

                    messages.success(
                        self.request,
                        f"Your purchase of <b>{total_credits}</b> credits "
                        "has been successful",
                        "credits_top_up",
                    )

                    payment_intent.status = PaymentIntentStatus.succeeded
                    payment_intent.save()
                    return HttpResponseRedirect(
                        reverse(
                            "certifyingorganisation-detail",
                            kwargs={"slug": organisation.slug},
                        )
                    )
            except PaymentIntent.DoesNotExist:
                pass

            return HttpResponseRedirect("/")


class CreateCheckoutSessionView(LoginRequiredMixin, TemplateView):
    """
     * Create a Stripe Checkout Session (for a new and a returning customer)
     * Add SUBSCRIBER_CUSTOMER_KEY to metadata to populate customer
     * Fill out Payment Form and Complete Payment
    Redirects the User to Stripe Checkout Session.
    This does a logged in purchase for a new and a returning customer using
    Stripe Checkout
    """

    template_name = "checkout.html"

    # An upper bound on a single purchase, so that a crafted "unit" cannot ask
    # Stripe for an absurd line item.
    maximum_credits = 100000

    def get_context_data(self, **kwargs):
        """
        Creates and returns a Stripe Checkout Session
        """
        # Get Parent Context
        context = super().get_context_data(**kwargs)

        org_id = self.request.GET.get("org", None)

        # Only the number of credits is taken from the client. The price used
        # to come from a "total" query parameter as well, which the top-up
        # page worked out in JavaScript - so the buyer set their own price.
        # "unit=10000&total=1" gave int(100 / 10000) = 0 cents per credit,
        # and the credits_quantity metadata below is what the success handler
        # credits the organisation with.
        try:
            unit = int(self.request.GET.get("unit", "0"))
        except (TypeError, ValueError):
            raise Http404()

        if unit <= 0 or unit > self.maximum_credits:
            raise Http404()

        try:
            org = CertifyingOrganisation.objects.get(id=org_id)
        except CertifyingOrganisation.DoesNotExist:
            raise Http404()

        # Credits are spent by the organisation, so buying them is an act on
        # that organisation and needs the same check as any other.
        if not user_can_manage_organisation(self.request.user, org):
            raise PermissionDenied(
                _("You may only buy credits for your own organisation.")
            )

        project = org.project
        unit_amount = int(Decimal(project.credit_cost or 0) * 100)
        if unit_amount <= 0:
            raise Http404()
        total = unit_amount * unit

        description = f"Top up credits for {org.name}"

        # to initialise Stripe.js on the front end
        context["STRIPE_PUBLIC_KEY"] = djstripe_settings.STRIPE_PUBLIC_KEY

        success_url = self.request.build_absolute_uri(reverse("checkout-success"))
        success_url += "?session_id={CHECKOUT_SESSION_ID}"

        cancel_url = self.request.build_absolute_uri(
            reverse("top-up", kwargs={"organisation_slug": org.slug})
        )

        try:
            logo = self.request.build_absolute_uri(org.project.image_file.url)
        except ValueError:
            logo = ""

        # get the id of the Model instance of
        # djstripe_settings.get_subscriber_model()
        # here we have assumed it is the Django User model.
        # It could be a Team, Company model too.
        # note that it needs to have an email field.
        id = self.request.user.id
        metadata = {
            f"{djstripe_settings.SUBSCRIBER_CUSTOMER_KEY}": id,
            "organisation_id": org.id,
            "credits_quantity": unit,
        }

        try:
            # Retrieve the Stripe Customer.
            customer = Customer.objects.get(subscriber=self.request.user)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                customer=customer.id,
                payment_intent_data={
                    "setup_future_usage": "off_session",
                    "metadata": metadata,
                },
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "unit_amount": unit_amount,
                            "product_data": {
                                "name": "Top up credits",
                                "images": [logo],
                                "description": description,
                            },
                        },
                        "quantity": unit,
                    },
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )

        except Customer.DoesNotExist:
            print("Customer Object not in DB.")

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                payment_intent_data={
                    "setup_future_usage": "off_session",
                    "metadata": metadata,
                },
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "unit_amount": unit_amount,
                            "product_data": {
                                "name": "Top up credits",
                                "images": [logo],
                                "description": description,
                            },
                        },
                        "quantity": unit,
                    },
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )

        # Create payment intent
        PaymentIntent.objects.create(
            id=session.id,
            amount=total,
            amount_received=0,
            amount_capturable=0,
            payment_method_types=["card"],
            status=PaymentIntentStatus.requires_payment_method,
        )

        context["CHECKOUT_SESSION_ID"] = session.id

        return context
