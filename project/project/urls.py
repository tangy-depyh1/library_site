from django.contrib import admin
from django.urls import include, path
from library.staff_views import staff_settings

urlpatterns = [
    path("admin/settings/", staff_settings, name="admin_settings"),
    path("admin/", admin.site.urls),
    path("", include("library.urls")),
]