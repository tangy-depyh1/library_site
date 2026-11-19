from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with_page(context, page):
    params = context["request"].GET.copy()
    params["page"] = page
    return params.urlencode()


@register.filter
def elided(paginator, number):
    return paginator.get_elided_page_range(number, on_each_side=1, on_ends=1)