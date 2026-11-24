import re
from importlib.util import find_spec
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class SecuritySettingsTests(SimpleTestCase):
    def test_secret_key_is_not_committed_as_a_literal(self):
        settings_module = find_spec(settings.SETTINGS_MODULE)
        self.assertIsNotNone(settings_module)
        source = Path(settings_module.origin).read_text(encoding="utf-8")

        self.assertNotRegex(source, re.compile(r"(?m)^\s*SECRET_KEY\s*=\s*['\"]"))
