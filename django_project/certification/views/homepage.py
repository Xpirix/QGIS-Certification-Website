from typing import Any

from certification.views.certifying_organisation import CertifyingOrganisationListView
from certification.utilities import world_map_data
from django.utils.timezone import now
from datetime import timedelta
from certification.models.course import Course, listed_courses
from django.views.generic import ListView


class UpcomingCourseListView(ListView):
    model = Course
    context_object_name = 'upcoming_courses'

    def get_queryset(self):
        """Return courses with start_date in the future and within the next 6 months."""
        three_months_from_now = now() + timedelta(days=180)
        return listed_courses().filter(
            start_date__gte=now(),
            start_date__lte=three_months_from_now
        ).order_by('start_date')


class HomepageView(CertifyingOrganisationListView):
    template_name = 'layouts/homepage.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Combine context from CertifyingOrganisationListView and UpcomingCourseListView."""
        context = super().get_context_data(**kwargs)
        upcoming_courses = UpcomingCourseListView().get_queryset()
        context['upcoming_courses'] = upcoming_courses
        context['world_map'] = world_map_data(
            self.get_queryset().filter(is_archived=False)
        )
        return context
