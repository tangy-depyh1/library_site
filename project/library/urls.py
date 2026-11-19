from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("rules/", views.rules, name="rules"),
    path("login/", views.login_page, name="login"),
]