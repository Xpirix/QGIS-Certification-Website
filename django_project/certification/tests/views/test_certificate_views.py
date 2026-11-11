# coding=utf-8
import logging
import tempfile
import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch

from base.tests.model_factories import ProjectF
from certification.models import Certificate
from certification.tests.model_factories import (
    AttendeeF,
    CertificateF,
    CertificateTypeF,
    CertifyingOrganisationF,
    CourseConvenerF,
    CourseF,
    CourseTypeF,
    TrainingCenterF,
)
from certification.views.certificate import (
    draw_verification_qr_code,
    generate_pdf,
    regenerate_all_certificate,
    regenerate_certificate,
)
from core.model_factories import UserF
from django.core import mail
from django.test import TestCase, override_settings
from django.test.client import Client, RequestFactory
from django.urls import reverse
from PIL import Image
from reportlab.pdfgen import canvas


class TestCertificateView(TestCase):
    """Test that certificate detail view and generating certificate works."""

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
            **{
                "username": "anita",
                "password": "password",
                "is_staff": True,
            }
        )
        self.user.set_password("password")
        self.user.save()

        self.user2 = UserF.create(
            **{
                "username": "anita2",
                "password": "password",
                "is_staff": True,
                "first_name": "Anita",
                "last_name": "Hapsari",
            }
        )
        self.user.set_password("password")
        self.user.save()

        self.project = ProjectF.create(
            owner=self.user, project_representative=self.user2
        )
        self.certifying_organisation = CertifyingOrganisationF.create(
            project=self.project
        )
        self.course_convener = CourseConvenerF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.training_center = TrainingCenterF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course_type = CourseTypeF.create(
            certifying_organisation=self.certifying_organisation
        )
        self.course = CourseF.create(
            course_convener=self.course_convener,
            certifying_organisation=self.certifying_organisation,
            course_type=self.course_type,
            training_center=self.training_center,
        )
        self.attendee = AttendeeF.create(
            certifying_organisation=self.certifying_organisation,
        )
        self.certificate_type = CertificateTypeF.create()
        self.certificate = CertificateF.create(
            course=self.course,
            attendee=self.attendee,
            author=self.user,
            certificate_type=self.certificate_type,
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
        # Redundant under TestCase's transaction rollback, and impossible now
        # that the relations are PROTECTed: it deleted parents before children.

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_generate_certificate(self, mock_open, mock_make_dirs, mock_exists):
        mock_open.return_value = MagicMock()
        mock_exists.return_value = False
        client = Client(HTTP_HOST="testserver")
        client.login(username="anita", password="password")
        response = client.get(
            reverse(
                "print-certificate",
                kwargs={
                    "organisation_slug": self.certifying_organisation.slug,
                    "course_slug": self.course.slug,
                    "pk": self.attendee.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 200)

    def get_temporary_image(self, temp_file):
        size = (200, 200)
        color = (255, 0, 0, 0)
        image = Image.new("RGBA", size, color)
        image.save(temp_file, "png")
        return temp_file

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    @patch("reportlab.lib.utils.ImageReader")
    def test_generate_certificate_with_signature(
        self, mock_open, mock_make_dirs, mock_exists, mock_image
    ):
        mock_open.return_value = MagicMock()
        mock_exists.return_value = False
        mock_image.return_value = MagicMock()

        temp_file = tempfile.NamedTemporaryFile()
        test_image = self.get_temporary_image(temp_file)

        signature = test_image.name
        self.project.project_representative_signature = signature
        self.project.save()

        self.course_convener.signature = signature
        self.course_convener.save()

        client = Client(HTTP_HOST="testserver")
        client.login(username="anita", password="password")
        response = client.get(
            reverse(
                "print-certificate",
                kwargs={
                    "organisation_slug": self.certifying_organisation.slug,
                    "course_slug": self.course.slug,
                    "pk": self.attendee.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.project.project_representative_signature = None
        self.project.save()
        self.course_convener.signature = None
        self.course_convener.save()

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_regenerate_certificate_allowed_user(
        self, mock_open, mock_make_dirs, mock_exists
    ):
        mock_open.return_value = MagicMock()
        mock_exists.return_value = False
        request = RequestFactory(HTTP_HOST="testserver")
        request.user = self.user
        request.method = "POST"
        request.META = {"HTTP_HOST": "testserver"}
        response = regenerate_certificate(
            request,
            project_slug=self.project.slug,
            organisation_slug=self.certifying_organisation.slug,
            course_slug=self.course.slug,
            pk=self.attendee.pk,
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("certification.views.certificate.generate_pdf")
    @patch("os.path.exists", return_value=False)
    @patch("os.makedirs")
    def test_regenerate_certificate_of_another_organisation_not_found(
        self, mock_make_dirs, mock_exists, mock_generate
    ):
        other_organisation = CertifyingOrganisationF.create(project=self.project)
        other_owner = UserF.create(username="other-owner")
        other_owner.set_password("password")
        other_owner.save()
        other_organisation.organisation_owners.add(other_owner)

        client = Client(HTTP_HOST="testserver")
        client.login(username="other-owner", password="password")
        response = client.post(
            reverse(
                "regenerate-certificate",
                kwargs={
                    "organisation_slug": other_organisation.slug,
                    "course_slug": self.course.slug,
                    "pk": self.attendee.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    @patch("django.contrib.messages.success")
    @patch("os.remove")
    @patch("certification.views.certificate.generate_pdf")
    def test_regenerate_all_certificate_allowed_user(
        self,
        mock_open,
        mock_make_dirs,
        mock_exists,
        mock_message,
        mock_remove,
        mock_generate_pdf,
    ):
        mock_message.return_value = MagicMock()
        mock_open.return_value = MagicMock()
        mock_remove.return_value = MagicMock()
        mock_generate_pdf.return_value = MagicMock()
        mock_exists.return_value = False
        request = RequestFactory(HTTP_HOST="testserver")
        request.user = self.user
        request.method = "POST"
        request.META = {"HTTP_HOST": "testserver"}
        response = regenerate_all_certificate(
            request,
            project_slug=self.project.slug,
            organisation_slug=self.certifying_organisation.slug,
            course_slug=self.course.slug,
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_detail_certificate(self):
        client = Client()
        response = client.get(
            reverse("certificate-details", kwargs={"id": str(self.certificate.uuid)})
        )
        self.assertEqual(response.status_code, 200)
        expected_templates = ["certificate/detail.html"]
        self.assertEqual(response.template_name, expected_templates)
        self.assertEqual(response.context["certificate"], self.certificate)

    # Certificates created before uuid links existed have no uuid. Once paid,
    # their old ID and print links keep working.
    def make_legacy(self, is_paid=True):
        Certificate.objects.filter(pk=self.certificate.pk).update(
            uuid=None, is_paid=is_paid
        )
        self.certificate.refresh_from_db()

    def get_detail(self, key):
        return Client().get(reverse("certificate-details", kwargs={"id": key}))

    def print_url(self):
        return reverse(
            "print-certificate",
            kwargs={
                "organisation_slug": self.certifying_organisation.slug,
                "course_slug": self.course.slug,
                "pk": self.attendee.pk,
            },
        )

    def test_new_certificate_gets_random_uuid(self):
        other = CertificateF.create(
            course=self.course,
            attendee=AttendeeF.create(
                certifying_organisation=self.certifying_organisation
            ),
            author=self.user,
            certificate_type=self.certificate_type,
        )
        self.assertEqual(self.certificate.uuid.version, 4)
        self.assertNotEqual(self.certificate.uuid, other.uuid)
        self.assertFalse(self.certificate.legacy_link)
        self.assertEqual(self.certificate.public_id, str(self.certificate.uuid))
        self.assertEqual(self.certificate.pdf_filename, f"{self.certificate.uuid}.pdf")
        self.assertEqual(
            self.certificate.get_absolute_url(),
            reverse("certificate-details", kwargs={"id": str(self.certificate.uuid)}),
        )

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_new_certificate_not_found_by_sequential_id(self):
        response = self.get_detail(self.certificate.certificateID)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("certificate"))

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_legacy_certificate_found_by_sequential_id(self):
        self.make_legacy()
        self.assertEqual(
            self.certificate.pdf_filename,
            f"{self.certificate.certificateID}.pdf",
        )
        self.assertEqual(self.certificate.public_id, self.certificate.certificateID)
        response = self.get_detail(self.certificate.certificateID)
        self.assertEqual(response.context["certificate"], self.certificate)
        self.assertContains(response, f"ID: {self.certificate.certificateID}")
        self.assertNotContains(response, "Verification code")

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_detail_page_shows_the_uuid_as_a_verification_code(self):
        response = self.get_detail(str(self.certificate.uuid))
        self.assertEqual(response.context["certificate"], self.certificate)
        self.assertContains(response, "Verification code")
        self.assertNotContains(response, f"ID: {self.certificate.uuid}")

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_unknown_uuid_not_found(self):
        response = self.get_detail("6f1c2b7e-0d3a-4c5e-9b8f-1a2b3c4d5e6f")
        self.assertIsNone(response.context.get("certificate"))

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_unpaid_legacy_certificate_not_found_by_sequential_id(self):
        self.make_legacy(is_paid=False)
        response = self.get_detail(self.certificate.certificateID)
        self.assertIsNone(response.context.get("certificate"))

    def test_paying_a_legacy_certificate_gives_it_a_uuid(self):
        self.make_legacy(is_paid=False)
        self.certificate.is_paid = True
        self.certificate.save()
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.uuid.version, 4)
        self.assertFalse(self.certificate.legacy_link)

    def test_saving_a_paid_legacy_certificate_keeps_its_old_links(self):
        self.make_legacy()
        self.certificate.save()
        self.certificate.refresh_from_db()
        self.assertIsNone(self.certificate.uuid)
        self.assertTrue(self.certificate.legacy_link)

    @patch("certification.views.certificate.renderPDF.draw")
    @patch("certification.views.certificate.canvas.Canvas")
    def test_pdf_prints_a_qr_code_of_the_verification_link(
        self, mock_canvas, mock_draw
    ):
        self.certificate.is_paid = True
        self.draw_pdf()
        link = f"https://testserver/en/certificate/{self.certificate.uuid}/"
        drawing = mock_draw.call_args.args[0]
        self.assertEqual(drawing.contents[0].value, link)
        self.assertEqual(drawing.contents[0].barLevel, "H")

        page = mock_canvas.return_value
        images = [call.args[0] for call in page.drawImage.call_args_list]
        self.assertTrue(any(str(image).endswith("qgis-sign.png") for image in images))
        lines = [call.args[-1] for call in page.drawString.call_args_list]
        self.assertIn(f"You can verify this certificate by scanning the QR Code or visiting {link}.", lines)
        self.assertFalse(any(line.startswith("ID:") for line in lines))

    @patch("certification.views.certificate.renderPDF.draw")
    @patch("certification.views.certificate.canvas.Canvas")
    def test_pdf_prints_the_old_id_on_a_legacy_certificate(
        self, mock_canvas, mock_draw
    ):
        self.make_legacy()
        self.draw_pdf()
        page = mock_canvas.return_value
        lines = [call.args[-1] for call in page.drawString.call_args_list]
        self.assertIn(f"ID: {self.certificate.certificateID}", lines)
        mock_draw.assert_not_called()

    def test_qr_code_renders_on_a_real_page(self):
        output = BytesIO()
        page = canvas.Canvas(output)
        draw_verification_qr_code(
            page, f"https://testserver/en/certificate/{uuid.uuid4()}/", 0, 0, 100
        )
        page.save()
        self.assertTrue(output.getvalue().startswith(b"%PDF"))

    def draw_pdf(self) -> None:
        generate_pdf(
            "unused.pdf",
            self.project,
            self.course,
            self.attendee,
            self.certificate,
            "testserver",
        )

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("certification.views.certificate.generate_pdf")
    @patch("os.path.exists", return_value=False)
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_print_link_hidden_from_public_for_new_certificate(
        self, mock_open, mock_make_dirs, mock_exists, mock_generate
    ):
        response = Client(HTTP_HOST="testserver").get(self.print_url())
        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("certification.views.certificate.generate_pdf")
    @patch("os.path.exists", return_value=False)
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_print_link_public_for_legacy_certificate(
        self, mock_open, mock_make_dirs, mock_exists, mock_generate
    ):
        self.make_legacy()
        response = Client(HTTP_HOST="testserver").get(self.print_url())
        self.assertEqual(response.status_code, 200)
        pathname = mock_generate.call_args[0][0]
        self.assertTrue(pathname.endswith(f"/{self.certificate.certificateID}.pdf"))

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    @patch("certification.views.certificate.generate_pdf")
    @patch("os.path.exists", return_value=False)
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_uuid_pdf_link_is_public(
        self, mock_open, mock_make_dirs, mock_exists, mock_generate
    ):
        response = Client(HTTP_HOST="testserver").get(
            reverse("certificate-pdf", kwargs={"uuid": self.certificate.uuid})
        )
        self.assertEqual(response.status_code, 200)
        pathname = mock_generate.call_args[0][0]
        self.assertTrue(pathname.endswith(f"/{self.certificate.uuid}.pdf"))

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_unknown_uuid_pdf_link_not_found(self):
        response = Client(HTTP_HOST="testserver").get(
            reverse(
                "certificate-pdf",
                kwargs={"uuid": "6f1c2b7e-0d3a-4c5e-9b8f-1a2b3c4d5e6f"},
            )
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(
        VALID_DOMAIN=[
            "testserver",
        ]
    )
    def test_email_uses_uuid_link_for_new_certificate(self):
        self.certificate.is_paid = True
        self.certificate.save()
        client = Client(HTTP_HOST="testserver")
        client.login(username="anita", password="password")
        client.post(
            reverse(
                "send_email",
                kwargs={
                    "organisation_slug": self.certifying_organisation.slug,
                    "course_slug": self.course.slug,
                },
            )
        )
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn(f"/en/certificate/{self.certificate.uuid}/pdf/", body)
        self.assertNotIn("/print/", body)
