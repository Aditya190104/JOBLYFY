from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return "?" + params.urlencode()


from django.utils.html import format_html
from django.templatetags.static import static


@register.simple_tag
def icon(name):
    return format_html(
        '<svg class="icon" aria-hidden="true" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><use href="{}#{}"></use></svg>',
        static("images/icons.svg"),
        name,
    )
