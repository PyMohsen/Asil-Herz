from .cart import serialize_cart
from .models import Category


def store_globals(request):
    """Provide navigation categories and session-backed cart summary to all templates."""
    cart_count, cart_total, cart_items = serialize_cart(request.session.get('cart', {}))

    return {
        'nav_categories': Category.objects.all(),
        'cart_count': cart_count,
        'cart_total': cart_total,
        'cart_items': cart_items,
    }
