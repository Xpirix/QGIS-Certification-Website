# coding=utf-8
"""Certificate model definitions for certification apps."""

import datetime
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .attendee import Attendee
from .certificate_type import CertificateType
from .course import Course


def increment_id(project):
    """Increment the certificate ID."""

    last_certificate = Certificate.objects.filter(
        course__certifying_organisation__project=project
    ).count()

    if last_certificate == 0:
        return "1"

    # get the latest certificate ID within a project
    list_certificates = Certificate.objects.filter(
        course__certifying_organisation__project=project
    ).values_list("certificateID", flat=True)
    certificate_array = []
    for certificate in list_certificates:
        number = f"{project.name}-".replace(" ", "")
        certificate_number = str(certificate).replace(number, "")
        certificate_array.append(int(certificate_number))

    new_int_id = max(certificate_array) + 1

    return new_int_id


class Certificate(models.Model):
    """Certificate model."""

    int_id = models.AutoField(primary_key=True)
    certificateID = models.CharField(max_length=100, blank=True, default="")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, null=True, editable=False)

    is_paid = models.BooleanField(
        help_text=_("Is this certificate paid?"), default=False
    )

    issue_date = models.DateField(auto_now_add=True, blank=True, null=True)

    certificate_type = models.ForeignKey(
        CertificateType, on_delete=models.PROTECT, null=True
    )

    author = models.ForeignKey(User, on_delete=models.PROTECT)
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    attendee = models.ForeignKey(Attendee, on_delete=models.PROTECT)
    objects = models.Manager()

    class Meta:
        ordering = ["certificateID"]
        unique_together = [
            "course",
            "attendee",
        ]

    def __unicode__(self):
        return self.certificateID

    def save(self, *args, **kwargs):
        """Save the certificate, giving it its IDs when they are due.

        A certificate created before uuid links existed has no uuid. If it
        was unpaid then and is paid now, it gets a uuid like a new one. One
        that was already paid keeps its old links.
        """

        if self.int_id is None:
            project_name = self.course.certifying_organisation.project.name
            words = project_name.replace(" ", "")
            increment_certificate = increment_id(
                self.course.certifying_organisation.project
            )
            self.certificateID = f"{words}-{increment_certificate}"
        elif (
            self.is_paid
            and self.uuid is None
            and not Certificate.objects.filter(pk=self.pk, is_paid=True).exists()
        ):
            self.uuid = uuid.uuid4()
        super(Certificate, self).save(*args, **kwargs)

    def get_absolute_url(self):
        """Return URL to certificate detail page.

        :return: URL
        :rtype: str
        """
        return reverse(
            "certificate-details",
            kwargs={
                "id": self.public_id,
            },
        )

    @property
    def legacy_link(self) -> bool:
        """Whether this certificate was created before uuid links existed.

        It has no uuid, and its old links by certificateID, or the print
        link by attendee pk, keep working once it is paid.

        :returns: True for a certificate without a uuid.
        :rtype: bool
        """

        return self.uuid is None

    @property
    def public_id(self) -> str:
        """The code printed on the certificate and used to look it up.

        New certificates show their uuid as a verification code, so it
        cannot be guessed. Legacy certificates keep the sequential ID they
        were issued with.

        :returns: The verification code, or the legacy certificate ID.
        :rtype: str
        """

        if self.legacy_link:
            return self.certificateID
        return str(self.uuid)

    @property
    def pdf_filename(self) -> str:
        """File name of the rendered PDF in the public media folder.

        It follows the public ID, so legacy files keep their names and new
        ones cannot be found by counting up IDs.

        :returns: The PDF file name.
        :rtype: str
        """

        return f"{self.public_id}.pdf"

    #: Days after issue during which a certificate may still be revoked.
    REVOCATION_WINDOW_DAYS = 7

    @property
    def is_revocable(self) -> bool:
        """Whether this certificate may still be revoked.

        Keyed to issue_date rather than the course end date. issue_date is
        auto_now_add and read-only in the admin, so it cannot be moved;
        Course.end_date is part of CourseForm, so keying the window to it
        would let anyone who can edit a course reopen the window at will.

        A certificate with no issue_date predates the field and is treated
        as a permanent record.

        :returns: True while the certificate is still within the window.
        :rtype: bool
        """

        if not self.issue_date:
            return False
        window_closes = self.issue_date + datetime.timedelta(
            days=self.REVOCATION_WINDOW_DAYS
        )
        return window_closes > datetime.date.today()
