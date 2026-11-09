# coding=utf-8
from datetime import datetime

from base.models.project import Project
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView, Response

from ..mixins import ActiveCertifyingOrganisationRequiredMixin
from ..models.certifying_organisation import CertifyingOrganisation
from ..models.course import Course, listed_courses
from ..serializers.course_serializer import CourseSerializer


class GetUpcomingCourseProject(APIView):
    """API returns GeoJSON location of upcoming courses within a project.
    The location is the location of the training center where this course
    will be held.

    Optional query parameter:
        - country: Filter courses by the organisation's country (ISO 3166-1 alpha-2 code).
          Supports single or multiple comma-separated codes.
          Example: /feed/upcoming-course/?country=ZA or /feed/upcoming-course/?country=ZA,MG,NL

    """

    def get(self, request):
        country_param = request.GET.get("country", None)
        try:
            today = datetime.today()
            project = Project.objects.get(slug="qgis")
            courses = listed_courses().filter(
                certifying_organisation__project=project, start_date__gte=today
            )
            if country_param:
                country_list = [
                    c.strip().upper() for c in country_param.split(",") if c.strip()
                ]
                if country_list:
                    courses = courses.filter(
                        certifying_organisation__country__in=country_list
                    )
            courses = courses.order_by("certifying_organisation__name", "start_date")
            serializer = CourseSerializer(courses, many=True)
            return Response(serializer.data)
        except Project.DoesNotExist:
            return HttpResponse(
                "Project does not exist.", status=status.HTTP_400_BAD_REQUEST
            )


class GetUpcomingCourseOrganisation(ActiveCertifyingOrganisationRequiredMixin, APIView):
    """API returns GeoJSON location of upcoming courses within a certifying
    organisation. The location is the location of the training center where
    this course will be held.

    """

    def get(self, request, organisation_slug):
        today = datetime.today()
        try:
            project = Project.objects.get(slug="qgis")
        except Project.DoesNotExist:
            return HttpResponse(
                "Project does not exist.", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            organisation = CertifyingOrganisation.objects.get(
                slug=organisation_slug, project=project
            )
        except Project.DoesNotExist:
            return HttpResponse(
                "Organisation does not exist.", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            courses = listed_courses().filter(
                certifying_organisation=organisation, start_date__gte=today
            ).order_by("start_date")
            serializer = CourseSerializer(courses, many=True)
            return Response(serializer.data)
        except Course.DoesNotExist:
            return HttpResponse(
                "Course does not exist.", status=status.HTTP_400_BAD_REQUEST
            )


class GetPastCourseProject(APIView):
    """API returns GeoJSON location of past courses within a project.
    The location is the location of the training center where this course
    will be held.

    """

    def get(self, request):
        try:
            today = datetime.today()
            project = Project.objects.get(slug="qgis")
            courses = listed_courses().filter(
                certifying_organisation__project=project, end_date__lte=today
            ).order_by("certifying_organisation__name", "start_date")
            serializer = CourseSerializer(courses, many=True)
            return Response(serializer.data)
        except Project.DoesNotExist:
            return HttpResponse(
                "Project does not exist.", status=status.HTTP_400_BAD_REQUEST
            )


class GetPastCourseOrganisation(ActiveCertifyingOrganisationRequiredMixin, APIView):
    """API returns GeoJSON location of past courses within a certifying
    organisation. The location is the location of the training center where
    this course will be held.

    """

    def get(self, request, organisation_slug):
        today = datetime.today()
        try:
            project = Project.objects.get(slug="qgis")
        except Project.DoesNotExist:
            return HttpResponse(
                "Project does not exist.", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            organisation = CertifyingOrganisation.objects.get(
                slug=organisation_slug, project=project
            )
        except Project.DoesNotExist:
            return HttpResponse(
                "Organisation does not exist.", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            courses = listed_courses().filter(
                certifying_organisation=organisation, end_date__lte=today
            ).order_by("start_date")
            serializer = CourseSerializer(courses, many=True)
            return Response(serializer.data)
        except Course.DoesNotExist:
            return HttpResponse(
                "Course does not exist.", status=status.HTTP_400_BAD_REQUEST
            )
