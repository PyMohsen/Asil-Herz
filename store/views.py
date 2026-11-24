import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, PositiveIntegerField, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Product
from .templatetags.store_filters import fa_digits

_FA_AR_DIGIT_TRANS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

RING_SIZES = [str(size) for size in range(56, 67)]
RING_SIZE_GUIDE = [
    {'size': '56', 'diameter': '۱۷٫۸', 'circumference': '۵۶'},
    {'size': '57', 'diameter': '۱۸٫۱', 'circumference': '۵۷'},
    {'size': '58', 'diameter': '۱۸٫۵', 'circumference': '۵۸'},
    {'size': '59', 'diameter': '۱۸٫۸', 'circumference': '۵۹'},
    {'size': '60', 'diameter': '۱۹٫۱', 'circumference': '۶۰'},
    {'size': '61', 'diameter': '۱۹٫۴', 'circumference': '۶۱'},
    {'size': '62', 'diameter': '۱۹٫۷', 'circumference': '۶۲'},
    {'size': '63', 'diameter': '۲۰٫۱', 'circumference': '۶۳'},
    {'size': '64', 'diameter': '۲۰٫۴', 'circumference': '۶۴'},
    {'size': '65', 'diameter': '۲۰٫۷', 'circumference': '۶۵'},
    {'size': '66', 'diameter': '۲۱٫۰', 'circumference': '۶۶'},
]

HIRZ_ENCLOSURE_OPTIONS = [
    'قاب نقره استوانه‌ای',
    'بازوبند چرمی دست‌دوز',
    'بدون قاب / لول‌شده',
]

SAMPLE_REVIEWS_BY_TYPE = {
    Product.ProductType.RING: [
        {
            'author': 'امیرحسین رضایی',
            'city': 'تهران',
            'date': '۱۴۰۴/۰۸/۱۲',
            'rating': 5,
            'comment': 'تراش سنگ و ظرافت قلم‌زنی رکاب نقره بسیار چشم‌نواز و تمیز بود. سایز طبق راهنمای سایت کاملاً اندازه شد و شناسنامه اصالت هم همراه بسته ارسال گردید.',
        },
        {
            'author': 'مهدی کریمی',
            'city': 'مشهد',
            'date': '۱۴۰۴/۰۷/۲۶',
            'rating': 5,
            'comment': 'بسته‌بندی نفیس و ارسال سریع با بیمه مرسوله باعث شد با خیال راحت خرید کنم. رنگ و شفافیت نگین در نور طبیعی فوق‌العاده است.',
        },
        {
            'author': 'زهرا شریفی',
            'city': 'اصفهان',
            'date': '۱۴۰۴/۰۶/۱۹',
            'rating': 4,
            'comment': 'برای هدیه تهیه کردم؛ وزن نقره بسیار استاندارد و پرداخت رکاب کاملاً حرفه‌ای انجام شده است.',
        },
    ],
    Product.ProductType.HIRZ: [
        {
            'author': 'سید محمد حسینی',
            'city': 'قم',
            'date': '۱۴۰۴/۰۸/۱۸',
            'rating': 5,
            'comment': 'کیفیت نگارش روی پوست آهو با خط ریز و خوانا به‌همراه گواهی معتبر رعایت آداب شرعی واقعاً اطمینان‌بخش بود. قاب نقره استوانه‌ای آب‌بندی بسیار خوبی دارد.',
        },
        {
            'author': 'فاطمه نوری',
            'city': 'شیراز',
            'date': '۱۴۰۴/۰۷/۳۰',
            'rating': 5,
            'comment': 'بازوبند چرمی دست‌دوز بسیار نرم، خوش‌دوخت و محکم است و اصلاً روی بازو احساس سنگینی یا اذیت نمی‌کند.',
        },
        {
            'author': 'علی‌اکبر موسوی',
            'city': 'تبریز',
            'date': '۱۴۰۴/۰۶/۲۴',
            'rating': 5,
            'comment': 'دقت در بسته‌بندی محترمانه، راهنمای کامل نحوه نگهداری و کیفیت متریال نقره و چرم مثال‌زدنی است.',
        },
    ],
}


def _parse_optional_price(raw_value: str) -> int | None:
    """Parse Persian or ASCII price strings into an integer or None."""
    if not raw_value:
        return None
    normalized = raw_value.translate(_FA_AR_DIGIT_TRANS).replace(',', '').replace('٬', '').strip()
    if not normalized.isdigit():
        return None
    return int(normalized)


def _serialize_cart(cart: dict) -> tuple[int, int, list[dict]]:
    """Compute cart count, total, and normalized item list from session cart."""
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
        items.append(
            {
                'key': key,
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
    return total_count, total_price, items


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
            | Q(short_description__icontains=query)
            | Q(sku__icontains=query)
            | Q(category__title__icontains=query)
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
        gallery_images.append({'url': product.main_image.url, 'alt': product.title})
    for img in product.images.all():
        gallery_images.append({'url': img.image.url, 'alt': img.alt_text or product.title})

    if product.product_type == Product.ProductType.RING:
        variant_options = [
            {'value': f'سایز {fa_digits(size)}', 'label': fa_digits(size), 'raw': size}
            for size in RING_SIZES
        ]
        default_variant = 'سایز ۶۰'
    else:
        variant_options = [
            {'value': option, 'label': option, 'raw': option}
            for option in HIRZ_ENCLOSURE_OPTIONS
        ]
        default_variant = HIRZ_ENCLOSURE_OPTIONS[0]

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
        'ring_size_guide': RING_SIZE_GUIDE,
        'reviews': SAMPLE_REVIEWS_BY_TYPE.get(product.product_type, []),
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
            return JsonResponse({'success': False, 'message': 'درخواست نامعتبر است.'}, status=400)
    else:
        payload = request.POST

    try:
        product_id = int(payload.get('product_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'شناسه محصول نامعتبر است.'}, status=400)

    product = get_object_or_404(Product, pk=product_id)

    if not product.is_in_stock:
        error_msg = 'متأسفانه این اثر در حال حاضر ناموجود است.'
        if is_json_request:
            return JsonResponse({'success': False, 'message': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect(product.get_absolute_url())

    try:
        quantity = max(1, int(payload.get('quantity', 1)))
    except (TypeError, ValueError):
        quantity = 1

    raw_variant = str(payload.get('variant', '')).strip()
    if product.product_type == Product.ProductType.RING:
        valid_ring_variants = {f'سایز {fa_digits(s)}' for s in RING_SIZES}
        variant = raw_variant if raw_variant in valid_ring_variants else 'سایز ۶۰'
    else:
        variant = raw_variant if raw_variant in HIRZ_ENCLOSURE_OPTIONS else HIRZ_ENCLOSURE_OPTIONS[0]

    cart = request.session.get('cart', {})
    item_key = f'{product.id}:{variant}'
    existing_qty = int(cart.get(item_key, {}).get('quantity', 0))
    new_qty = min(existing_qty + quantity, product.stock)
    added_qty = new_qty - existing_qty

    cart[item_key] = {
        'product_id': product.id,
        'title': product.title,
        'slug': product.slug,
        'sku': product.sku,
        'variant': variant,
        'quantity': new_qty,
        'unit_price': product.get_final_price,
        'image_url': product.main_image.url if product.main_image else '',
    }
    request.session['cart'] = cart
    request.session.modified = True

    cart_count, cart_total, cart_items = _serialize_cart(cart)

    if added_qty <= 0:
        notice = f'حداکثر موجودی «{product.title}» ({fa_digits(product.stock)} عدد) هم‌اکنون در سبد خرید شماست.'
    else:
        notice = f'«{product.title}» ({variant}) به سبد خرید اضافه شد.'

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
        notice = 'سبد خرید خالی شد.'
    elif item_key in cart:
        removed_title = cart[item_key].get('title', 'محصول')
        del cart[item_key]
        notice = f'«{removed_title}» از سبد خرید حذف شد.'
    else:
        notice = 'آیتم مورد نظر یافت نشد.'

    request.session['cart'] = cart
    request.session.modified = True

    cart_count, cart_total, cart_items = _serialize_cart(cart)
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
