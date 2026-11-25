import logging

from django.http import HttpResponse
from django.template.loader import get_template

logger = logging.getLogger(__name__)


def _error_response(template_name, status_code):
    template = get_template(template_name)
    return HttpResponse(
        template.render({"status_code": status_code}),
        status=status_code,
        content_type="text/html; charset=utf-8",
    )


def permission_denied(request, exception=None):
    logger.warning("HTTP 403 for path=%s", request.path)
    return _error_response("403.html", 403)


def page_not_found(request, exception=None):
    logger.warning("HTTP 404 for path=%s", request.path)
    return _error_response("404.html", 404)


def server_error(request):
    logger.error("HTTP 500 for path=%s", request.path)
    return _error_response("500.html", 500)
