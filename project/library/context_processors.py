def navigation(request):
    items = [("catalog", "Каталог"), ("rules", "Правила"), ("contacts", "Контакты")]
    if request.user.is_authenticated:
        items.append(("cabinet", "Личный кабинет"))
    current = getattr(request.resolver_match, "url_name", None)
    return {"nav_items": [{"name": n, "title": t, "active": n == current} for n, t in items]}