import re

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Product
from .templatetags.store_filters import fa_digits

_FA_AR_DIGIT_TRANS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

RING_SIZES = [str(size) for size in range(56, 67)]

HIRZ_ENCLOSURE_CHOICES = [
    ('silver_tube', _('Cylindrical silver case')),
    ('leather_armlet', _('Hand-stitched leather armlet')),
    ('unframed', _('Unframed / rolled scroll')),
]

_HIRZ_ALIAS_TO_CODE = {
    'silver_tube': 'silver_tube',
    'قاب نقره استوانه‌ای': 'silver_tube',
    'cylindrical silver case': 'silver_tube',
    'leather_armlet': 'leather_armlet',
    'بازوبند چرمی دست‌دوز': 'leather_armlet',
    'hand-stitched leather armlet': 'leather_armlet',
    'unframed': 'unframed',
    'بدون قاب / لول‌شده': 'unframed',
    'unframed / rolled scroll': 'unframed',
}

_HIRZ_CODE_TO_LABEL = dict(HIRZ_ENCLOSURE_CHOICES)


def format_ring_variant(size_code: str) -> str:
    """Format a ring size variant label in the active language."""
    return _('Size %(size)s') % {'size': fa_digits(size_code)}


def format_hirz_variant(enclosure_code: str) -> str:
    """Format a Hirz enclosure variant label in the active language."""
    label = _HIRZ_CODE_TO_LABEL.get(enclosure_code, HIRZ_ENCLOSURE_CHOICES[0][1])
    return str(label)


def resolve_variant(product: Product, raw_variant: str) -> tuple[str, str, str]:
    """Normalize incoming variant text into (variant_type, variant_code, localized_display)."""
    cleaned = (raw_variant or '').strip()
    if product.product_type == Product.ProductType.RING:
        ascii_val = cleaned.translate(_FA_AR_DIGIT_TRANS)
        match = re.search(r'\b(5[6-9]|6[0-6])\b', ascii_val)
        size_code = match.group(1) if match and match.group(1) in RING_SIZES else '60'
        return 'ring_size', size_code, format_ring_variant(size_code)

    code = _HIRZ_ALIAS_TO_CODE.get(cleaned.lower()) or _HIRZ_ALIAS_TO_CODE.get(cleaned) or 'silver_tube'
    return 'hirz_enclosure', code, format_hirz_variant(code)


def _localize_stored_variant(item: dict) -> str:
    """Return the localized variant label for a session cart entry."""
    variant_type = item.get('variant_type')
    variant_code = item.get('variant_code')
    if variant_type == 'ring_size' and variant_code:
        return format_ring_variant(str(variant_code))
    if variant_type == 'hirz_enclosure' and variant_code:
        return format_hirz_variant(str(variant_code))

    raw = str(item.get('variant', '')).strip()
    ascii_raw = raw.translate(_FA_AR_DIGIT_TRANS)
    match = re.search(r'\b(5[6-9]|6[0-6])\b', ascii_raw)
    if match:
        return format_ring_variant(match.group(1))
    alias_code = _HIRZ_ALIAS_TO_CODE.get(raw.lower()) or _HIRZ_ALIAS_TO_CODE.get(raw)
    if alias_code:
        return format_hirz_variant(alias_code)
    return raw


def serialize_cart(cart: dict) -> tuple[int, int, list[dict]]:
    """Compute cart count, total, and localized item list from session cart."""
    product_ids = [
        item.get('product_id')
        for item in cart.values()
        if int(item.get('quantity', 0)) > 0 and item.get('product_id')
    ]
    products_by_id = Product.objects.in_bulk(product_ids) if product_ids else {}

    items = []
    total_count = 0
    total_price = 0
    for key, item in cart.items():
        qty = int(item.get('quantity', 0))
        unit_price = int(item.get('unit_price', 0))
        if qty <= 0:
            continue
        subtotal = qty * unit_price
        total_count += qty
        total_price += subtotal

        product = products_by_id.get(item.get('product_id'))
        slug = product.slug if product else item.get('slug', '')
        title = product.localized_title if product else item.get('title', '')
        url = (
            product.get_absolute_url()
            if product
            else (reverse('store:product_detail', kwargs={'slug': slug}) if slug else '')
        )

        items.append(
            {
                'key': key,
                'product_id': item.get('product_id'),
                'title': title,
                'slug': slug,
                'url': url,
                'sku': item.get('sku', ''),
                'variant': _localize_stored_variant(item),
                'quantity': qty,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'image_url': item.get('image_url', ''),
            }
        )
    return total_count, total_price, items
