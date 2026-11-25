from django import template
from django.utils.translation import get_language, gettext as _

register = template.Library()

_PERSIAN_DIGIT_MAP = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
_ASCII_DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def is_persian_locale() -> bool:
    """Return True when the active Django language is Persian."""
    lang = (get_language() or 'fa').split('-')[0]
    return lang == 'fa'


@register.filter(name='fa_digits')
def fa_digits(value) -> str:
    """Format digits as Persian numerals in fa locale or ASCII numerals otherwise."""
    if value is None:
        return ''
    text = str(value)
    if is_persian_locale():
        return text.translate(_PERSIAN_DIGIT_MAP)
    return text.translate(_ASCII_DIGIT_MAP)


@register.filter(name='comma_fa')
def comma_fa(value) -> str:
    """Format an integer with thousand separators and locale-appropriate numerals."""
    if value is None or value == '':
        return ''
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return fa_digits(value)
    formatted = f'{numeric:,}'
    if is_persian_locale():
        return formatted.translate(_PERSIAN_DIGIT_MAP)
    return formatted


@register.filter(name='toman')
def toman(value) -> str:
    """Format a price with thousand separators, locale numerals, and Toman unit."""
    formatted = comma_fa(value)
    if not formatted:
        return ''
    unit = _('Toman')
    return f'{formatted} {unit}'


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs) -> str:
    """Return URL-encoded query parameters merging current GET params with overrides."""
    request = context.get('request')
    query = request.GET.copy() if request else {}
    for key, val in kwargs.items():
        if val is None or val == '':
            query.pop(key, None)
        else:
            query[key] = str(val)
    encoded = query.urlencode()
    return f'?{encoded}' if encoded else '?'
