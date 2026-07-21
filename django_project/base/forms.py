# coding=utf-8
import logging

from certification.forms import MultiSelectWidget, SingleUserSelectWidget
from common.utilities import format_user_display
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Field,
    Fieldset,
    Layout,
    Submit,
)
from django import forms
from django.contrib.auth.models import User
from django.contrib.flatpages.forms import FlatpageForm
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import Domain, Organisation, Project, ProjectFlatpage, ProjectScreenshot

logger = logging.getLogger(__name__)


class ProjectScreenshotForm(forms.ModelForm):
    """Form to input a screenshot linked to a project."""

    class Meta:
        model = ProjectScreenshot
        fields = ("screenshot",)

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.form_method = "post"
        layout = Layout(
            Fieldset(
                "Screenshot",
                Field("screenshot", css_class="form-control"),
                Field("DELETE", css_class="input-small"),
                css_id="project-form",
            )
        )
        self.helper.layout = layout
        self.helper.include_media = False
        self.helper.html5_required = False
        super(ProjectScreenshotForm, self).__init__(*args, **kwargs)


class ProjectForm(forms.ModelForm):
    """Form for creating projects."""

    certification_managers = forms.ModelMultipleChoiceField(
        queryset=User.objects.order_by("username"),
        widget=MultiSelectWidget(
            attrs={
                "get_list_url": "/autocomplete/users/",
                "get_item_url": "/get_user_by_pk/",
                "color_style": "is-success",
            }
        ),
        required=False,
        help_text=_(
            "Managers of the certification app in this project. "
            "They will receive email notification about organisation and have"
            " the same permissions as project owner in the certification app."
        ),
    )

    project_representative = forms.ModelChoiceField(
        queryset=User.objects.order_by("username"),
        widget=SingleUserSelectWidget(
            attrs={
                "get_list_url": "/autocomplete/users/",
                "get_item_url": "/get_user_by_pk/",
                "color_style": "is-success",
            }
        ),
        required=False,
        help_text=_(
            "Project representative. "
            "This name will be used on invoices and certificates. "
        ),
    )

    # noinspection PyClassicStyleClass
    class Meta:
        """Meta class."""

        model = Project
        fields = (
            "name",
            "organisation",
            "image_file",
            "accent_color",
            "description",
            "project_url",
            "project_repository_url",
            "precis",
            "gitter_room",
            "project_representative",
            "project_representative_signature",
            "certification_managers",
            "credit_cost",
            "certificate_credit",
            "template_certifying_organisation_certificate",
            "is_certification",
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.helper = FormHelper()
        self.helper.form_tag = False
        layout = Layout(
            Fieldset(
                "Project details",
                Field("name", css_class="form-control"),
                Field("organisation", css_class="form-control"),
                Field("image_file", css_class="form-control"),
                Field("accent_color", css_class="form-control"),
                Field("description", css_class="form-control"),
                Field("project_url", css_class="form-control"),
                Field("project_repository_url", css_class="form-control"),
                Field("precis", css_class="form-control"),
                Field("project_representative",
                      template="crispy/user_picker_field.html"),
                Field("project_representative_signature", css_class="form-control"),
                Field("certification_managers",
                      template="crispy/user_picker_field.html"),
                Field("credit_cost", css_class="form-control"),
                Field("certificate_credit", css_class="form-control"),
                Field("gitter_room", css_class="form-control"),
                Field("is_certification"),
                css_id="project-form",
            ),
            Field(
                "template_certifying_organisation_certificate", css_class="form-control"
            ),
        )
        self.helper.layout = layout
        self.helper.include_media = False
        self.helper.html5_required = False
        super(ProjectForm, self).__init__(*args, **kwargs)
        self.fields["certification_managers"].label_from_instance = (
            format_user_display
        )
        self.fields["project_representative"].label_from_instance = (
            format_user_display
        )
        # self.helper.add_input(Submit('submit', 'Submit', css_class='button is-success pt-2 mt-5'))
        self.fields["is_certification"].label = "Enable Certification"

    def save(self, commit=True):
        instance = super(ProjectForm, self).save(commit=False)
        instance.approved = True
        instance.owner = self.user
        instance.save()
        self.save_m2m()
        return instance


# Screenshot formset
ScreenshotFormset = inlineformset_factory(
    Project, ProjectScreenshot, form=ProjectScreenshotForm, extra=5
)


class SignupForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="First Name (Optional)",
        required=False,
        widget=forms.TextInput({"placeholder": _("First Name")}),
    )

    last_name = forms.CharField(
        max_length=150,
        label="Last Name (Optional)",
        required=False,
        widget=forms.TextInput({"placeholder": _("Last Name")}),
    )

    def signup(self, request, user):
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save()


class RegisterDomainForm(forms.ModelForm):
    """Form to register a domain."""

    # noinspection PyClassicStyleClass
    class Meta:
        """Meta class."""

        model = Domain
        fields = (
            "domain",
            "role",
            "project",
            "organisation",
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        form_title = "Register a Domain"
        self.helper = FormHelper()
        layout = Layout(
            Fieldset(
                form_title,
                Field("domain", css_class="form-control"),
                Field("role", css_class="form-control"),
                Field("project", css_class="form-control"),
                Field("organisation", css_class="form-control"),
            )
        )
        self.helper.layout = layout
        self.helper.html5_required = False
        super(RegisterDomainForm, self).__init__(*args, **kwargs)
        self.helper.add_input(
            Submit("submit", "Submit", css_class="button is-success pt-2 mt-5")
        )

    def save(self, commit=True):
        instance = super(RegisterDomainForm, self).save(commit=False)
        instance.user = self.user
        instance.save()
        return instance


class OrganisationForm(forms.ModelForm):
    """Form to create an organisation that is associated to a project."""

    # noinspection PyClassicStyleClass
    class Meta:
        """Meta class."""

        model = Organisation
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        form_title = "Create an Organisation"
        self.helper = FormHelper()
        layout = Layout(
            Fieldset(
                form_title,
                Field("name", css_class="form-control"),
            )
        )
        self.helper.layout = layout
        self.helper.html5_required = False
        super(OrganisationForm, self).__init__(*args, **kwargs)
        self.helper.add_input(
            Submit("submit", "Submit", css_class="button is-success pt-2 mt-5")
        )

    def save(self, commit=True):
        instance = super(OrganisationForm, self).save(commit=False)
        instance.owner = self.user
        instance.save()
        return instance


class UserForm(forms.ModelForm):
    """Form to update user profile."""

    # noinspection PyClassicStyleClass.
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        form_title = "<h1>Update User Profile</h1>"
        self.helper = FormHelper()
        layout = Layout(
            Fieldset(
                form_title,
                Field("username", css_class="form-control"),
                Field("first_name", css_class="form-control"),
                Field("last_name", css_class="form-control"),
                Field("email", css_class="form-control"),
            )
        )
        self.helper.layout = layout
        self.helper.html5_required = False
        super(UserForm, self).__init__(*args, **kwargs)
        self.helper.add_input(
            Submit("submit", "Submit", css_class="button is-success pt-2 mt-5")
        )


class ProjectFlatpageForm(FlatpageForm):
    class Meta:
        model = ProjectFlatpage
        fields = "__all__"
