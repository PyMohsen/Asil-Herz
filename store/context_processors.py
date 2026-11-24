from .models import Category


def store_globals(request):
    """Provide navigation categories and session-backed cart summary to all templates."""
    cart = request.session.get('cart', {})
    cart_items = []
    cart_count = 0
    cart_total = 0

    for item_key, item in cart.items():
        qty = int(item.get('quantity', 0))
        unit_price = int(item.get('unit_price', 0))
        if qty <= 0:
            continue
        subtotal = qty * unit_price
        cart_count += qty
        cart_total += subtotal
        cart_items.append(
            {
                'key': item_key,
                'product_id': item.get('product_id'),
                'title': item.get('title', ''),
                'slug': item.get('slug', ''),
                'sku': item.get('sku', ''),
                'variant': item.get('variant', ''),
                'quantity': qty,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'image_url': item.get('image_url', ''),
            }
        )

    return {
        'nav_categories': Category.objects.all(),
        'cart_count': cart_count,
        'cart_total': cart_total,
        'cart_items': cart_items,
    }
