import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, PositiveIntegerField, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .cart import (
    HIRZ_ENCLOSURE_CHOICES,
    RING_SIZES,
    format_hirz_variant,
    format_ring_variant,
    resolve_variant,
    serialize_cart,
)
from .models import Category, Product
from .templatetags.store_filters import fa_digits, is_persian_locale

_FA_AR_DIGIT_TRANS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

_RING_SIZE_GUIDE_BASE = [
    ('56', '17.8'),
    ('57', '18.1'),
    ('58', '18.5'),
    ('59', '18.8'),
    ('60', '19.1'),
    ('61', '19.4'),
    ('62', '19.7'),
    ('63', '20.1'),
    ('64', '20.4'),
    ('65', '20.7'),
    ('66', '21.0'),
]


def _get_sample_reviews(product_type: str) -> list[dict]:
    """Return localized sample customer reviews for the given product type."""
    if product_type == Product.ProductType.RING:
        return [
            {
                'author': _('Amirhossein Rezaei'),
                'city': _('Tehran'),
                'date': _('2025/11/03'),
                'rating': 5,
                'comment': _(
                    'The gemstone cut and hand-engraving on the silver band were remarkably refined and clean. '
                    'The sizing matched the site guide accurately, and the authenticity certificate arrived with the package.'
                ),
            },
            {
                'author': _('Mehdi Karimi'),
                'city': _('Mashhad'),
                'date': _('2025/10/18'),
                'rating': 5,
                'comment': _(
                    'Luxury packaging and fast insured shipping made the purchase completely worry-free. '
                    'The color and clarity of the gemstone in natural daylight are extraordinary.'
                ),
            },
            {
                'author': _('Zahra Sharifi'),
                'city': _('Isfahan'),
                'date': _('2025/09/10'),
                'rating': 4,
                'comment': _(
                    'Ordered as a gift; the silver weight feels very balanced and the finishing of the band is truly artisanal.'
                ),
            },
        ]
    return [
        {
            'author': _('Seyed Mohammad Hosseini'),
            'city': _('Qom'),
            'date': _('2025/11/09'),
            'rating': 5,
            'comment': _(
                'The fine legible calligraphy on deerskin parchment together with the verified ritual compliance certificate was truly reassuring. '
                'The cylindrical silver case seals tightly.'
            ),
        },
        {
            'author': _('Fatemeh Nouri'),
            'city': _('Shiraz'),
            'date': _('2025/10/22'),
            'rating': 5,
            'comment': _(
                'The hand-stitched leather armlet is very soft, neatly sewn, and sturdy, feeling comfortable and light on the arm.'
            ),
        },
        {
            'author': _('Ali-Akbar Mousavi'),
            'city': _('Tabriz'),
            'date': _('2025/09/15'),
            'rating': 5,
            'comment': _(
                'The respectful presentation, thorough care instructions, and quality of the silver and leather are exemplary.'
            ),
        },
    ]


def _parse_optional_price(raw_value: str) -> int | None:
    """Parse Persian or ASCII price strings into an integer or None."""
    if not raw_value:
        return None
    normalized = raw_value.translate(_FA_AR_DIGIT_TRANS).replace(',', '').replace('٬', '').strip()
    if not normalized.isdigit():
        return None
    return int(normalized)


def home_view(request):
    """Render storefront home page with hero showcase, categories, and featured products."""
    categories = Category.objects.annotate(product_count=Count('products')).order_by('id')
    featured_products = (
        Product.objects.select_related('category')
        .filter(is_featured=True)
        .order_by('-created_at')[:8]
    )
    hero_ring = (
        Product.objects.select_related('category')
        .filter(product_type=Product.ProductType.RING, is_featured=True)
        .first()
    )
    hero_hirz = (
        Product.objects.select_related('category')
        .filter(product_type=Product.ProductType.HIRZ, is_featured=True)
        .first()
    )

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'hero_ring': hero_ring,
        'hero_hirz': hero_hirz,
    }
    return render(request, 'store/home.html', context)


def product_list_view(request):
    """Render filterable, sortable, and paginated product catalog."""
    products_qs = Product.objects.select_related('category').annotate(
        effective_price=Case(
            When(
                discount_price__isnull=False,
                discount_price__gt=0,
                discount_price__lt=F('price'),
                then=F('discount_price'),
            ),
            default=F('price'),
            output_field=PositiveIntegerField(),
        )
    )

    category_slug = request.GET.get('category', '').strip()
    product_type = request.GET.get('type', '').strip()
    min_price_raw = request.GET.get('min_price', '').strip()
    max_price_raw = request.GET.get('max_price', '').strip()
    in_stock = request.GET.get('in_stock', '') in ('1', 'true', 'on')
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'newest').strip()

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        products_qs = products_qs.filter(category__slug=category_slug)

    if product_type in (Product.ProductType.RING, Product.ProductType.HIRZ):
        products_qs = products_qs.filter(product_type=product_type)
    else:
        product_type = ''

    min_price = _parse_optional_price(min_price_raw)
    if min_price is not None:
        products_qs = products_qs.filter(effective_price__gte=min_price)

    max_price = _parse_optional_price(max_price_raw)
    if max_price is not None:
        products_qs = products_qs.filter(effective_price__lte=max_price)

    if in_stock:
        products_qs = products_qs.filter(stock__gt=0)

    if query:
        products_qs = products_qs.filter(
            Q(title__icontains=query)
            | Q(title_en__icontains=query)
            | Q(short_description__icontains=query)
            | Q(short_description_en__icontains=query)
            | Q(sku__icontains=query)
            | Q(category__title__icontains=query)
            | Q(category__title_en__icontains=query)
        )

    sort_map = {
        'newest': ('-created_at', '-id'),
        'cheapest': ('effective_price', '-created_at'),
        'most_expensive': ('-effective_price', '-created_at'),
    }
    if sort not in sort_map:
        sort = 'newest'
    products_qs = products_qs.order_by(*sort_map[sort])

    total_count = products_qs.count()
    paginator = Paginator(products_qs, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.annotate(product_count=Count('products')).order_by('id')
    has_active_filters = any(
        [category_slug, product_type, min_price is not None, max_price is not None, in_stock, query]
    )

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'total_count': total_count,
        'categories': categories,
        'active_category': active_category,
        'selected_category': category_slug,
        'selected_type': product_type,
        'min_price': min_price_raw,
        'max_price': max_price_raw,
        'in_stock': in_stock,
        'query': query,
        'sort': sort,
        'has_active_filters': has_active_filters,
    }
    return render(request, 'store/product_list.html', context)


def product_detail_view(request, slug):
    """Render product detail page with gallery, conditional variants, specs, reviews, and related products."""
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('images', 'specifications'),
        slug=slug,
    )

    gallery_images = []
    if product.main_image:
        gallery_images.append({'url': product.main_image.url, 'alt': product.localized_title})
    for img in product.images.all():
        gallery_images.append({'url': img.image.url, 'alt': img.localized_alt_text})

    if product.product_type == Product.ProductType.RING:
        variant_options = [
            {'value': format_ring_variant(size), 'label': fa_digits(size), 'raw': size}
            for size in RING_SIZES
        ]
        default_variant = format_ring_variant('60')
    else:
        variant_options = [
            {'value': format_hirz_variant(code), 'label': format_hirz_variant(code), 'raw': code}
            for code, _label in HIRZ_ENCLOSURE_CHOICES
        ]
        default_variant = format_hirz_variant(HIRZ_ENCLOSURE_CHOICES[0][0])

    use_fa_decimal = is_persian_locale()
    ring_size_guide = [
        {
            'size': size,
            'variant_value': format_ring_variant(size),
            'diameter': fa_digits(diam).replace('.', '٫') if use_fa_decimal else diam,
            'circumference': fa_digits(size),
        }
        for size, diam in _RING_SIZE_GUIDE_BASE
    ]

    related_products = (
        Product.objects.select_related('category')
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by('-created_at')[:4]
    )

    context = {
        'product': product,
        'gallery_images': gallery_images,
        'variant_options': variant_options,
        'default_variant': default_variant,
        'ring_size_guide': ring_size_guide,
        'reviews': _get_sample_reviews(product.product_type),
        'related_products': related_products,
    }
    return render(request, 'store/product_detail.html', context)


@require_POST
def add_to_cart_view(request):
    """Add product, variant, and quantity to session-backed cart."""
    is_json_request = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.content_type or '')
        or 'application/json' in request.headers.get('Accept', '')
    )

    if 'application/json' in (request.content_type or ''):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': _('Invalid request.')}, status=400)
    else:
        payload = request.POST

    try:
        product_id = int(payload.get('product_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': _('Invalid product ID.')}, status=400)

    product = get_object_or_404(Product, pk=product_id)

    if not product.is_in_stock:
        error_msg = _('Unfortunately, this item is currently out of stock.')
        if is_json_request:
            return JsonResponse({'success': False, 'message': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect(product.get_absolute_url())

    try:
        quantity = max(1, int(payload.get('quantity', 1)))
    except (TypeError, ValueError):
        quantity = 1

    raw_variant = str(payload.get('variant', '')).strip()
    variant_type, variant_code, variant = resolve_variant(product, raw_variant)

    cart = request.session.get('cart', {})
    item_key = f'{product.id}:{variant}'
    existing_qty = int(cart.get(item_key, {}).get('quantity', 0))
    new_qty = min(existing_qty + quantity, product.stock)
    added_qty = new_qty - existing_qty

    cart[item_key] = {
        'product_id': product.id,
        'title': product.title,
        'title_en': product.title_en,
        'slug': product.slug,
        'sku': product.sku,
        'variant': variant,
        'variant_type': variant_type,
        'variant_code': variant_code,
        'quantity': new_qty,
        'unit_price': product.get_final_price,
        'image_url': product.main_image.url if product.main_image else '',
    }
    request.session['cart'] = cart
    request.session.modified = True

    cart_count, cart_total, cart_items = serialize_cart(cart)

    if added_qty <= 0:
        notice = _('All available stock of "%(title)s" (%(stock)s units) is already in your cart.') % {
            'title': product.localized_title,
            'stock': fa_digits(product.stock),
        }
    else:
        notice = _('"%(title)s" (%(variant)s) has been added to your cart.') % {
            'title': product.localized_title,
            'variant': variant,
        }

    if is_json_request:
        return JsonResponse(
            {
                'success': True,
                'message': notice,
                'cart_count': cart_count,
                'cart_total': cart_total,
                'cart_items': cart_items,
            }
        )

    messages.success(request, notice)
    return redirect(product.get_absolute_url())


@require_POST
def remove_from_cart_view(request):
    """Remove an item or clear session-backed cart."""
    is_json_request = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.content_type or '')
        or 'application/json' in request.headers.get('Accept', '')
    )

    if 'application/json' in (request.content_type or ''):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST

    item_key = str(payload.get('item_key', '')).strip()
    cart = request.session.get('cart', {})

    if item_key == '__all__':
        cart = {}
        notice = _('Your cart has been cleared.')
    elif item_key in cart:
        removed_item = cart[item_key]
        product = Product.objects.filter(pk=removed_item.get('product_id')).first()
        removed_title = (
            product.localized_title if product else removed_item.get('title') or _('Product')
        )
        del cart[item_key]
        notice = _('"%(title)s" was removed from your cart.') % {'title': removed_title}
    else:
        notice = _('Item not found in cart.')

    request.session['cart'] = cart
    request.session.modified = True

    cart_count, cart_total, cart_items = serialize_cart(cart)
    if is_json_request:
        return JsonResponse(
            {
                'success': True,
                'message': notice,
                'cart_count': cart_count,
                'cart_total': cart_total,
                'cart_items': cart_items,
            }
        )

    return redirect(request.META.get('HTTP_REFERER') or 'store:home')
