from django.contrib import admin
from django.urls import include, path
from library.staff_views import staff_settings
from library.error_views import page_not_found, permission_denied, server_error

handler403 = permission_denied
handler404 = page_not_found
handler500 = server_error

urlpatterns = [
    path("admin/settings/", staff_settings, name="admin_settings"),
    path("admin/", admin.site.urls),
    path("", include("library.urls")),
]