from certification.models import CertifyingOrganisation, Course, CourseConvener
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

# Views reach these mixins with either a signed-in user or an AnonymousUser,
# and both are asked the same permission questions.
UserOrAnonymous = AbstractBaseUser | AnonymousUser


def user_can_manage_organisation(
    user: UserOrAnonymous,
    certifying_organisation: CertifyingOrganisation,
) -> bool:
    """Check whether a user may create, modify or delete objects of an
    organisation.

    This is the single source of truth for the rule that the templates
    already express when they decide whether to show the edit and delete
    buttons. Keep it in step with course/detail.html and
    course_type/detail.html.

    :param user: The user requesting the action.
    :type user: User

    :param certifying_organisation: The organisation owning the object.
    :type certifying_organisation: CertifyingOrganisation

    :returns: True if the user is allowed to manage the organisation.
    :rtype: bool
    """

    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True

    project = certifying_organisation.project
    return (
        certifying_organisation.organisation_owners.filter(pk=user.pk).exists()
        or project.certification_managers.filter(pk=user.pk).exists()
        or user == project.owner
    )


class ActiveCertifyingOrganisationRequiredMixin:
    """Mixin to ensure that the certifyin organisation is not archived."""

    def dispatch(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        organisation_slug = kwargs.get("organisation_slug") or kwargs.get("slug")
        try:
            organisation = CertifyingOrganisation.objects.get(slug=organisation_slug)
        except CertifyingOrganisation.DoesNotExist:
            raise Http404("Organisation does not exist.")
        if organisation.is_archived:
            raise Http404("This organisation is archived.")
        return super().dispatch(request, *args, **kwargs)


class OrganisationEditPermissionMixin:
    """Enforce, on the server, who may modify an organisation's objects.

    Until this existed the rule was applied only by hiding buttons in the
    templates, which any user could bypass by requesting the URL directly.

    The certifying organisation is resolved here, before ``get()`` and
    ``post()`` run, so that permission is decided before the view touches
    the object.
    """

    def get_permission_organisation(self) -> CertifyingOrganisation:
        """Resolve the organisation this request acts on.

        :returns: The certifying organisation named in the URL.
        :rtype: CertifyingOrganisation
        :raises: Http404
        """

        slug = self.kwargs.get("organisation_slug") or self.kwargs.get("slug")
        try:
            return CertifyingOrganisation.objects.get(slug=slug)
        except CertifyingOrganisation.DoesNotExist:
            raise Http404("Sorry! We could not find your certifying organisation!")

    def user_has_edit_permission(
        self,
        user: UserOrAnonymous,
        organisation: CertifyingOrganisation,
    ) -> bool:
        """Hook for subclasses that allow additional users.

        :returns: True if the user may modify objects of this organisation.
        :rtype: bool
        """

        return user_can_manage_organisation(user, organisation)

    def dispatch(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        organisation = self.get_permission_organisation()

        # Make these available to get()/post()/get_queryset(), which several
        # of these views set for themselves and then rely on.
        self.organisation_slug = organisation.slug
        self.certifying_organisation = organisation

        if not self.user_has_edit_permission(request.user, organisation):
            raise PermissionDenied(
                _("You do not have permission to modify this organisation.")
            )
        return super().dispatch(request, *args, **kwargs)


class CourseEditPermissionMixin(OrganisationEditPermissionMixin):
    """Course permissions: as the organisation, plus course conveners.

    The organisation detail page offers a convener the "Create New Course"
    button and the course detail page offers them edit and delete, so both
    cases are allowed here: creating a course anywhere in their organisation,
    and changing a course they convene.
    """

    def user_has_edit_permission(
        self,
        user: UserOrAnonymous,
        organisation: CertifyingOrganisation,
    ) -> bool:
        if super().user_has_edit_permission(user, organisation):
            return True
        if not user.is_authenticated:
            return False

        course_slug = self.kwargs.get("slug")
        if course_slug is None:
            # Creating: any convener of this organisation may add a course.
            return CourseConvener.objects.filter(
                certifying_organisation=organisation, user=user
            ).exists()

        # Looked up directly rather than through self.get_object(), which
        # depends on attributes the view only sets once get()/post() runs.
        return Course.objects.filter(
            certifying_organisation=organisation,
            slug=course_slug,
            course_convener__user=user,
        ).exists()


class ProtectChildrenDeleteMixin:
    """Refuse to delete an object while dependent records still exist.

    The foreign keys pointing at Course and CourseType cascade, so deleting
    a parent would take its children - including issued certificates - with
    it. Rather than delete silently, the user is told what to remove first.

    Note for Django >= 4.0: DeleteView deletes through FormMixin, so
    ``delete()`` is no longer called on POST; the guard has to hook
    ``post()``. Both delete views end their own ``post()`` with
    ``super().post(...)``, so listing this mixin before DeleteView is enough
    to run it.
    """

    def get_blocking_children(self) -> list[tuple[str, int]]:
        """Describe the dependants that prevent deletion.

        :returns: (label, count) for each non-empty relation.
        :rtype: list
        """

        raise NotImplementedError(
            "Subclasses of ProtectChildrenDeleteMixin must implement "
            "get_blocking_children()."
        )

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        if getattr(self, "object", None) is not None:
            context["blocking_children"] = self.get_blocking_children()
        return context

    def get_blocked_message(
        self, blocking_children: list[tuple[str, int]]
    ) -> str:
        """Build the message shown when deletion is refused."""

        summary = ", ".join(
            "%d %s" % (count, label) for label, count in blocking_children
        )
        return _(
            "This %(object)s cannot be deleted because it still has "
            "%(summary)s. Please remove them first."
        ) % {"object": self.model._meta.verbose_name, "summary": summary}

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        self.object = self.get_object()
        blocking_children = self.get_blocking_children()
        if blocking_children:
            messages.error(request, self.get_blocked_message(blocking_children))
            return self.render_to_response(self.get_context_data(object=self.object))
        return super().post(request, *args, **kwargs)
