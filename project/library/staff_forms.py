from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Author,
    Book,
    BookAuthor,
    Copy,
    Genre,
    LibrarySettings,
    Reader,
    Staff,
)
from .forms import StyledFormMixin

class StaffAccountCreationForm(UserCreationForm):
    full_name = forms.CharField(label="ФИО", max_length=150)
    role = forms.ChoiceField(label="Роль", choices=Staff.Role.choices)
    position = forms.CharField(label="Должность", max_length=100, required=False)

    class Meta:
        model = get_user_model()
        fields = ("username",)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Staff.objects.create(
                user=user,
                full_name=self.cleaned_data["full_name"],
                role=self.cleaned_data["role"],
                position=self.cleaned_data["position"],
            )
        return user


class ReaderRegistrationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Reader
        fields = ["card_number", "full_name", "group_name", "phone", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["card_number"].help_text = "Введите ровно 6 цифр без пробелов."
        self.fields["full_name"].help_text = "Укажите фамилию, имя и отчество."


class IssueLoanForm(forms.Form):
    card_number = forms.CharField(label="Номер читательского билета", max_length=6)
    inventory_number = forms.CharField(label="Инвентарный номер экземпляра", max_length=6)


class ReturnLoanForm(forms.Form):
    inventory_number = forms.CharField(label="Инвентарный номер экземпляра", max_length=6)
    condition = forms.ChoiceField(
        label="Состояние при возврате",
        choices=Copy.Condition.choices,
        initial=Copy.Condition.GOOD,
    )


class LibrarySettingsForm(forms.ModelForm):
    class Meta:
        model = LibrarySettings
        fields = [
            "fine_per_day",
            "loan_days",
            "renewal_days",
            "max_renewals",
            "reservation_hold_days",
            "reminder_days",
        ]


class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ["name", "description"]


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ["last_name", "first_name", "middle_name", "birth_year"]


class BookForm(forms.ModelForm):
    authors = forms.ModelMultipleChoiceField(
        label="Авторы",
        queryset=Author.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    class Meta:
        model = Book
        fields = [
            "title",
            "genre",
            "isbn",
            "publisher",
            "year_published",
            "pages",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["authors"].initial = self.instance.authors.all()

    def save(self, commit=True):
        book = super().save(commit=commit)
        if commit:
            BookAuthor.objects.filter(book=book).delete()
            BookAuthor.objects.bulk_create(
                [
                    BookAuthor(book=book, author=author, position=position)
                    for position, author in enumerate(self.cleaned_data["authors"], 1)
                ]
            )
        return book


class CopyForm(forms.ModelForm):
    class Meta:
        model = Copy
        fields = [
            "book",
            "inventory_number",
            "status",
            "condition",
            "shelf_location",
            "acquired_date",
            "written_off_date",
        ]
