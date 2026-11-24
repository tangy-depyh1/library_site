from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView
from .forms import LoginForm
from . import views
from .reader_workflow_views import create_reservation

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/book/<int:pk>/", views.book_detail, name="book_detail"),
    path("catalog/book/<int:book_id>/reserve/", create_reservation, name="reserve"),
    path("catalog/book/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("search/", views.search, name="search"),
    path("contacts/", views.contacts, name="contacts"),
    path("rules/", TemplateView.as_view(template_name="rules.html"), name="rules"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cabinet/", views.cabinet, name="cabinet"),
    path("cabinet/favorites/", views.favorites, name="favorites"),
    path("cabinet/profile/", views.profile, name="profile"),
    path("api/books/", views.api_search, name="api_search"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html", authentication_form=LoginForm), name="login"),
    path("", include("library.staff_views")),
    path("", include("library.reader_workflow_views")),
]