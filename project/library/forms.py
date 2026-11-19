import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import Reader

PHONE_RE = r"^\+?\d[\d\s\-()]{9,17}$"
phone_validator = RegexValidator(PHONE_RE, "Введите телефон в формате +7 900 123-45-67.")


class StyledFormMixin:
    """CSS-классы полям, атрибуты длины для JS и пометка полей с ошибками."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "select" if isinstance(field.widget, forms.Select) else "input"
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " " + css).strip()
            if getattr(field, "min_length", None):
                field.widget.attrs["minlength"] = field.min_length
            if getattr(field, "max_length", None):
                field.widget.attrs["maxlength"] = field.max_length

    def is_valid(self):
        valid = super().is_valid()
        for name in self.errors:
            if name in self.fields:
                attrs = self.fields[name].widget.attrs
                attrs["class"] += " is-error"
                attrs["aria-invalid"] = "true"
        return valid


class ContactForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="Ваше имя", min_length=2, max_length=100)
    email = forms.EmailField(label="E-mail для ответа")
    phone = forms.CharField(label="Телефон", required=False, validators=[phone_validator],
                            help_text="Необязательно. Формат: +7 900 123-45-67")
    message = forms.CharField(label="Вопрос библиотекарю", min_length=10, max_length=500,
                              widget=forms.Textarea(attrs={"rows": 5}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["data-type"] = "email"
        self.fields["phone"].widget.attrs["data-type"] = "phone"


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Reader
        fields = ["phone", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["data-type"] = "email"
        self.fields["phone"].widget.attrs["data-type"] = "phone"
        self.fields["phone"].help_text = "Формат: +7 900 123-45-67"

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not re.match(PHONE_RE, phone):
            raise ValidationError("Введите телефон в формате +7 900 123-45-67.")
        return phone


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Логин (reader_ и номер билета)"