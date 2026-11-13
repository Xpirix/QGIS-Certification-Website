from django.shortcuts import render


def docs_overview(request):
    """
    Renders the overview page
    """
    return render(
        request,
        "docs/overview.html",
        {},
    )


def docs_cert_manager(request):
    """
    Renders the cert_manager page
    """
    return render(
        request,
        "docs/cert_manager.html",
        {},
    )


def docs_register_cert_org(request):
  """
  Renders the registering a certifying organisation page
  """
  return render(
    request,
    "docs/register_cert_org.html",
    {},
  )


def docs_approval_cert_org(request):
  """
  Renders the approval process for certifying organisations page
  """
  return render(
    request,
    "docs/approval_cert_org.html",
    {},
  )


def docs_manage_cert_org(request):
  """
  Renders the managing your certifying organisation page
  """
  return render(
    request,
    "docs/manage_cert_org.html",
    {},
  )


def docs_training_centers(request):
  """
  Renders the training centers page
  """
  return render(
    request,
    "docs/training_centers.html",
    {},
  )


def docs_course_conveners(request):
  """
  Renders the course conveners page
  """
  return render(
    request,
    "docs/course_conveners.html",
    {},
  )


def docs_course_types(request):
  """
  Renders the course types page
  """
  return render(
    request,
    "docs/course_types.html",
    {},
  )


def docs_courses(request):
  """
  Renders the courses page
  """
  return render(
    request,
    "docs/courses.html",
    {},
  )


def docs_create_certificate_template(request):
  """
  Renders the creating a certificate template page
  """
  return render(
    request,
    "docs/create_certificate_template.html",
    {},
  )


def docs_payments(request):
  """
  Renders the payments page
  """
  return render(
    request,
    "docs/payments.html",
    {},
  )


def docs_issuing_certificates(request):
  """
  Renders the issuing certificates page
  """
  return render(
    request,
    "docs/issuing_certificates.html",
    {},
  )


def docs_getting_help(request):
  """
  Renders the getting help page
  """
  return render(
    request,
    "docs/getting_help.html",
    {},
  )


def docs_faq(request):
  """
  Renders the FAQ page
  """
  return render(
    request,
    "docs/faq.html",
    {},
  )
