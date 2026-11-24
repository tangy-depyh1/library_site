from django.test import TestCase
from django.urls import reverse


class LoginRouteTests(TestCase):
    def test_login_route_uses_reader_specific_username_label(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Логин (reader_ и номер билета)")
