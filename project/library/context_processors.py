def navigation(request):
    items = [("catalog", "Каталог"), ("rules", "Правила"), ("contacts", "Контакты")]
    if request.user.is_authenticated:
        items.append(("cabinet", "Личный кабинет"))
        try:
            role = request.user.staff_profile.role
        except AttributeError:
            role = None
        if role == "librarian":
            items.append(("staff_dashboard", "Библиотекарю"))
        elif role == "admin":
            items.extend(
                [
                    ("staff_accounts", "Сотрудники"),
                    ("staff_settings", "Настройки"),
                ]
            )
    current = getattr(request.resolver_match, "url_name", None)
    return {"nav_items": [{"name": n, "title": t, "active": n == current} for n, t in items]}