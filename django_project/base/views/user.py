# coding=utf-8
from django.db.models import QuerySet
from django.urls import reverse
from braces.views import LoginRequiredMixin
from django.views.generic import UpdateView, TemplateView
from django.contrib.auth.models import User
from ..forms import UserForm


class UserDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'account/profile.html'

    def get_context_data(self, **kwargs):
        context = super(UserDetailView, self).get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = 'account/update.html'
    context_object_name = 'user'

    def get_queryset(self) -> QuerySet:
        """Restrict the view to the requesting user's own record.

        The check has to live here rather than in get_context_data(). Django
        calls get_context_data() when it renders the form and when the form
        fails validation, but a successful POST goes straight from
        get_object() to form_valid() to a redirect, so a check placed there
        guarded the page and not the update. Scoping the queryset makes
        get_object() raise Http404 on every method instead.

        :returns: A queryset containing only the requesting user.
        :rtype: QuerySet
        """

        return User.objects.filter(pk=self.request.user.pk)

    def get_form_kwargs(self):
        """Get keyword arguments from form.

        :returns keyword argument from the form
        :rtype: dict
        """

        kwargs = super(UserUpdateView, self).get_form_kwargs()
        kwargs.update({
            'user': self.request.user,
        })
        return kwargs

    def get_success_url(self):
        """Define the redirect URL.

        After successful update of the object, the user will be redirected to
        the user profile page.

        :returns: URL
        :rtype: HttpResponse
        """

        return reverse('user-profile')
