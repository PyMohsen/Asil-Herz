from django import template

register = template.Library()

_PERSIAN_DIGIT_MAP = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


@register.filter(name='fa_digits')
def fa_digits(value) -> str:
    """Convert Latin digits in a string or number to Persian numerals."""
    if value is None:
        return ''
    return str(value).translate(_PERSIAN_DIGIT_MAP)


@register.filter(name='comma_fa')
def comma_fa(value) -> str:
    """Format an integer with comma thousand-separators and Persian numerals."""
    if value is None or value == '':
        return ''
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return fa_digits(value)
    return f'{numeric:,}'.translate(_PERSIAN_DIGIT_MAP)


@register.filter(name='toman')
def toman(value) -> str:
    """Format a price with comma thousand-separators, Persian digits, and Toman unit."""
    formatted = comma_fa(value)
    if not formatted:
        return ''
    return f'{formatted} تومان'


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
