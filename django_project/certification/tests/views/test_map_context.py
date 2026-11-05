# coding=utf-8
import logging

from certification.tests.model_factories import (
    CertifyingOrganisationF,
    ProjectF,
    TrainingCenterF,
)
from certification.utilities import training_center_map_data, world_map_data
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse


class TestWorldMapData(TestCase):
    """Organisations are grouped by country for the world map."""

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.project = ProjectF.create()

    def test_groups_organisations_by_country(self) -> None:
        first = CertifyingOrganisationF.create(project=self.project, country="ZA")
        second = CertifyingOrganisationF.create(project=self.project, country="ZA")
        third = CertifyingOrganisationF.create(
            project=self.project, country="MG", url="https://example.org"
        )

        data = world_map_data([first, second, third])

        self.assertEqual(set(data), {"ZA", "MG"})
        self.assertEqual(data["ZA"]["count"], 2)
        self.assertEqual(data["MG"]["count"], 1)
        self.assertEqual(
            data["MG"]["organisations"],
            [
                {
                    "name": third.name,
                    "url": third.get_absolute_url(),
                    "logo": None,
                    "website": "https://example.org",
                    "slug": third.slug,
                    "lon": None,
                    "lat": None,
                }
            ],
        )

    def test_marker_goes_at_first_located_training_centre(self) -> None:
        organisation = CertifyingOrganisationF.create(project=self.project, country="MG")
        TrainingCenterF.create(certifying_organisation=organisation)
        TrainingCenterF.create(
            certifying_organisation=organisation,
            location=Point(x=47.5, y=-18.9, srid=4326),
        )
        TrainingCenterF.create(
            certifying_organisation=organisation,
            location=Point(x=49.4, y=-18.1, srid=4326),
        )

        marker = world_map_data([organisation])["MG"]["organisations"][0]

        self.assertEqual((marker["lon"], marker["lat"]), (47.5, -18.9))

    def test_listed_organisation_uses_its_second_located_centre(self) -> None:
        organisation = CertifyingOrganisationF.create(
            project=self.project, country="MG", name="QGIS Qtibia Engineering"
        )
        TrainingCenterF.create(
            certifying_organisation=organisation,
            location=Point(x=47.5, y=-18.9, srid=4326),
        )
        TrainingCenterF.create(
            certifying_organisation=organisation,
            location=Point(x=49.4, y=-18.1, srid=4326),
        )

        marker = world_map_data([organisation])["MG"]["organisations"][0]

        self.assertEqual((marker["lon"], marker["lat"]), (49.4, -18.1))

    def test_listed_organisation_with_one_centre_uses_it(self) -> None:
        organisation = CertifyingOrganisationF.create(
            project=self.project, country="MG", name="QGIS Qtibia Engineering"
        )
        TrainingCenterF.create(
            certifying_organisation=organisation,
            location=Point(x=47.5, y=-18.9, srid=4326),
        )

        marker = world_map_data([organisation])["MG"]["organisations"][0]

        self.assertEqual((marker["lon"], marker["lat"]), (47.5, -18.9))

    def test_organisation_without_located_centre_has_no_marker(self) -> None:
        organisation = CertifyingOrganisationF.create(project=self.project, country="MG")
        TrainingCenterF.create(certifying_organisation=organisation)

        marker = world_map_data([organisation])["MG"]["organisations"][0]

        self.assertIsNone(marker["lon"])
        self.assertIsNone(marker["lat"])

    def test_no_organisations_gives_an_empty_map(self) -> None:
        self.assertEqual(world_map_data([]), {})


class TestTrainingCenterMapData(TestCase):
    """Training centres become markers on a country map."""

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.organisation = CertifyingOrganisationF.create(
            project=ProjectF.create(), country="MG"
        )

    def test_marker_carries_longitude_then_latitude(self) -> None:
        center = TrainingCenterF.create(
            certifying_organisation=self.organisation,
            slug="antananarivo-centre",
            location=Point(x=47.5, y=-18.9, srid=4326),
        )

        data = training_center_map_data([center], self.organisation)

        self.assertEqual(data["country"], "MG")
        self.assertEqual(data["organisation"], self.organisation.name)
        self.assertIsNone(data["logo"])
        marker = data["markers"][0]
        self.assertEqual((marker["lon"], marker["lat"]), (47.5, -18.9))
        self.assertEqual(marker["address"], center.address)
        self.assertEqual(
            marker["url"],
            reverse(
                "trainingcenter-detail",
                kwargs={
                    "organisation_slug": self.organisation.slug,
                    "slug": "antananarivo-centre",
                },
            ),
        )

    def test_centres_without_a_location_are_left_out(self) -> None:
        TrainingCenterF.create(certifying_organisation=self.organisation)

        data = training_center_map_data(
            self.organisation.trainingcenter_set.all(), self.organisation
        )

        self.assertEqual(data["markers"], [])


class TestMapContextInViews(TestCase):
    """Each page with a map hands the map its data."""

    @override_settings(VALID_DOMAIN=["testserver"])
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.client = Client()
        self.client.post("/set_language/", data={"language": "en"})
        self.project = ProjectF.create()
        self.organisation = CertifyingOrganisationF.create(
            project=self.project, country="MG"
        )
        self.center = TrainingCenterF.create(
            certifying_organisation=self.organisation,
            slug="antananarivo-centre",
            location=Point(x=47.5, y=-18.9, srid=4326),
        )

    @override_settings(VALID_DOMAIN=["testserver"])
    def test_homepage_has_world_map(self) -> None:
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["world_map"]["MG"]["count"], 1)
        self.assertContains(response, 'id="map-data"')

    @override_settings(VALID_DOMAIN=["testserver"])
    def test_homepage_map_leaves_out_archived_organisations(self) -> None:
        CertifyingOrganisationF.create(project=self.project, country="MG", is_archived=True)
        CertifyingOrganisationF.create(project=self.project, country="FR", is_archived=True)

        response = self.client.get(reverse("home"))

        world_map = response.context["world_map"]
        self.assertEqual(world_map["MG"]["count"], 1)
        self.assertNotIn("FR", world_map)

    @override_settings(VALID_DOMAIN=["testserver"])
    def test_organisation_detail_has_site_map(self) -> None:
        response = self.client.get(
            reverse(
                "certifyingorganisation-detail",
                kwargs={"slug": self.organisation.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        site_map = response.context["site_map"]
        self.assertEqual(site_map["country"], "MG")
        self.assertEqual(len(site_map["markers"]), 1)
        self.assertContains(response, 'id="map-data"')

    @override_settings(VALID_DOMAIN=["testserver"])
    def test_training_center_detail_has_site_map(self) -> None:
        response = self.client.get(
            reverse(
                "trainingcenter-detail",
                kwargs={
                    "organisation_slug": self.organisation.slug,
                    "slug": self.center.slug,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        site_map = response.context["site_map"]
        self.assertEqual(site_map["country"], "MG")
        self.assertEqual(site_map["markers"][0]["name"], self.center.name)
