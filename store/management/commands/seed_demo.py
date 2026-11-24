from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from store.models import Category, Product, ProductImage, ProductSpecification


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _create_luxury_background(
    width: int,
    height: int,
    top_rgb: tuple[int, int, int],
    bottom_rgb: tuple[int, int, int],
    gold_rgb: tuple[int, int, int] = (200, 169, 106),
) -> Image.Image:
    """Create a smooth vertical gradient canvas with luxury double gold filigree frame."""
    img = Image.new('RGB', (width, height), top_rgb)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(1, height - 1)
        row_color = _lerp_color(top_rgb, bottom_rgb, t)
        draw.line([(0, y), (width, y)], fill=row_color)

    # Smooth continuous central spotlight halo
    cx, cy = width // 2, height // 2
    max_r = int(min(width, height) * 0.46)
    steps = 45
    for step in range(steps, 0, -1):
        t = 1.0 - (step / steps)
        r = int(max_r * (step / steps))
        halo = _lerp_color(top_rgb, (255, 252, 245), 0.16 * (t ** 1.4))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=halo)

    # Double luxury border
    m1, m2 = 22, 30
    draw.rectangle([m1, m1, width - m1, height - m1], outline=gold_rgb, width=2)
    draw.rectangle([m2, m2, width - m2, height - m2], outline=_lerp_color(gold_rgb, top_rgb, 0.35), width=1)

    # Corner diamond motifs
    for px, py in [(m1, m1), (width - m1, m1), (m1, height - m1), (width - m1, height - m1)]:
        d = 7
        draw.polygon([(px, py - d), (px + d, py), (px, py + d), (px - d, py)], fill=gold_rgb)

    return img


def _draw_ring_illustration(
    img: Image.Image,
    stone_rgb: tuple[int, int, int],
    stone_light: tuple[int, int, int],
    style_idx: int = 0,
) -> Image.Image:
    """Render a stylized handcrafted 925 silver ring with faceted natural gemstone."""
    w, h = img.size
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = w // 2, int(h * 0.54)

    # Soft translucent ground shadow
    draw.ellipse([cx - 125, cy + 95, cx + 125, cy + 132], fill=(20, 20, 18, 55))

    silver_dark = (128, 134, 140, 255)
    silver_mid = (196, 202, 208, 255)
    silver_bright = (236, 240, 244, 255)
    gold_trim = (200, 169, 106, 255)
    stone_rgba = (*stone_rgb, 255)
    light_rgba = (*stone_light, 255)
    mid_stone_rgba = (*_lerp_color(stone_rgb, stone_light, 0.34), 255)

    # Outer silver shank + transparent cutout so background gradient passes through
    draw.ellipse([cx - 122, cy - 62, cx + 122, cy + 112], fill=silver_dark, outline=(90, 96, 102, 255), width=3)
    draw.ellipse([cx - 114, cy - 54, cx + 114, cy + 104], fill=silver_mid)
    draw.ellipse([cx - 92, cy - 30, cx + 92, cy + 84], fill=(0, 0, 0, 0), outline=(142, 148, 154, 255), width=3)

    # Engraved side shoulders (Safavid / Filigree accent dots)
    for dx in (-104, -96, 96, 104):
        draw.ellipse([cx + dx - 5, cy + 8, cx + dx + 5, cy + 18], fill=gold_trim)

    # Bezel mount
    bezel_y = cy - 72
    if style_idx % 3 == 0:
        # Oval Safavid cabochon bezel
        draw.ellipse([cx - 72, bezel_y - 54, cx + 72, bezel_y + 54], fill=silver_dark, outline=(85, 92, 98, 255), width=3)
        draw.ellipse([cx - 64, bezel_y - 46, cx + 64, bezel_y + 46], fill=silver_bright, outline=gold_trim, width=2)
        draw.ellipse([cx - 56, bezel_y - 38, cx + 56, bezel_y + 38], fill=stone_rgba)
        draw.ellipse([cx - 42, bezel_y - 26, cx + 38, bezel_y + 22], fill=mid_stone_rgba)
        draw.ellipse([cx - 32, bezel_y - 22, cx - 2, bezel_y - 6], fill=light_rgba)
    elif style_idx % 3 == 1:
        # Octagonal emerald-cut bezel
        pts_outer = [
            (cx - 44, bezel_y - 54), (cx + 44, bezel_y - 54),
            (cx + 68, bezel_y - 30), (cx + 68, bezel_y + 30),
            (cx + 44, bezel_y + 54), (cx - 44, bezel_y + 54),
            (cx - 68, bezel_y + 30), (cx - 68, bezel_y - 30),
        ]
        pts_inner = [
            (cx - 34, bezel_y - 42), (cx + 34, bezel_y - 42),
            (cx + 54, bezel_y - 22), (cx + 54, bezel_y + 22),
            (cx + 34, bezel_y + 42), (cx - 34, bezel_y + 42),
            (cx - 54, bezel_y + 22), (cx - 54, bezel_y - 22),
        ]
        pts_table = [
            (cx - 20, bezel_y - 25), (cx + 20, bezel_y - 25),
            (cx + 32, bezel_y - 12), (cx + 32, bezel_y + 12),
            (cx + 20, bezel_y + 25), (cx - 20, bezel_y + 25),
            (cx - 32, bezel_y + 12), (cx - 32, bezel_y - 12),
        ]
        draw.polygon(pts_outer, fill=silver_bright, outline=(95, 100, 106, 255))
        draw.polygon(pts_inner, fill=stone_rgba, outline=gold_trim)
        draw.polygon(pts_table, fill=mid_stone_rgba)
        draw.line([(cx - 18, bezel_y - 16), (cx + 6, bezel_y - 16)], fill=light_rgba, width=4)
    else:
        # Teardrop / cushion royal bezel
        draw.ellipse([cx - 62, bezel_y - 52, cx + 62, bezel_y + 52], fill=silver_bright, outline=gold_trim, width=3)
        draw.ellipse([cx - 50, bezel_y - 40, cx + 50, bezel_y + 40], fill=stone_rgba)
        draw.chord([cx - 42, bezel_y - 34, cx + 42, bezel_y + 34], start=195, end=335, fill=light_rgba)
        draw.ellipse([cx - 34, bezel_y - 24, cx + 26, bezel_y + 16], fill=mid_stone_rgba)

    composited = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    img.paste(composited)
    return img


def _draw_hirz_illustration(
    img: Image.Image,
    leather_rgb: tuple[int, int, int],
    ribbon_rgb: tuple[int, int, int],
    style_idx: int = 0,
) -> Image.Image:
    """Render a stylized silver cylindrical Hirz capsule, deerskin scroll, and leather armlet."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2

    silver_dark = (126, 133, 140)
    silver_mid = (198, 204, 210)
    silver_hi = (238, 242, 246)
    gold = (200, 169, 106)
    parchment = (242, 229, 200)
    parchment_edge = (212, 192, 154)

    if style_idx % 2 == 0:
        # Leather armlet strap + centered engraved silver cylindrical tube
        strap_h = 68
        draw.rounded_rectangle(
            [cx - 210, cy - strap_h // 2 + 12, cx + 210, cy + strap_h // 2 + 12],
            radius=28,
            fill=leather_rgb,
            outline=(45, 32, 24),
            width=3,
        )
        # Hand-stitching dashes along leather strap
        for sx in range(cx - 190, cx + 190, 18):
            draw.line([(sx, cy - strap_h // 2 + 20), (sx + 9, cy - strap_h // 2 + 20)], fill=gold, width=2)
            draw.line([(sx, cy + strap_h // 2 + 4), (sx + 9, cy + strap_h // 2 + 4)], fill=gold, width=2)

        # Cylindrical silver Hirz case
        cap_w, cap_h = 210, 74
        draw.rounded_rectangle(
            [cx - cap_w // 2, cy - cap_h // 2 - 6, cx + cap_w // 2, cy + cap_h // 2 - 6],
            radius=32,
            fill=silver_mid,
            outline=silver_dark,
            width=3,
        )
        # Specular highlight bar along cylinder
        draw.rectangle([cx - cap_w // 2 + 24, cy - 26, cx + cap_w // 2 - 24, cy - 12], fill=silver_hi)
        # Gold engraved rings
        for rx in (-68, -24, 24, 68):
            draw.line([(cx + rx, cy - 41), (cx + rx, cy + 29)], fill=gold, width=4)
        # Central emerald/gold seal emblem
        draw.ellipse([cx - 14, cy - 20, cx + 14, cy + 8], fill=ribbon_rgb, outline=gold, width=2)

        # Deerskin parchment scroll resting below
        draw.rounded_rectangle([cx - 120, cy + 62, cx + 120, cy + 104], radius=16, fill=parchment, outline=parchment_edge, width=2)
        draw.rectangle([cx - 14, cy + 60, cx + 14, cy + 106], fill=ribbon_rgb, outline=gold, width=2)
    else:
        # Unrolled deerskin manuscript scroll + upright silver capsule
        # Scroll sheet
        draw.rounded_rectangle([cx - 175, cy - 95, cx + 65, cy + 95], radius=14, fill=parchment, outline=parchment_edge, width=3)
        # Stylized calligraphic text lines on deerskin
        for ly in range(cy - 64, cy + 70, 20):
            draw.line([(cx - 145, ly), (cx + 35, ly)], fill=(96, 78, 56), width=2)
        # Gold seal stamp on scroll
        draw.ellipse([cx - 145, cy + 32, cx - 105, cy + 72], fill=ribbon_rgb, outline=gold, width=3)

        # Silver cylindrical container beside scroll
        draw.rounded_rectangle([cx + 88, cy - 102, cx + 166, cy + 102], radius=34, fill=silver_mid, outline=silver_dark, width=3)
        draw.rectangle([cx + 104, cy - 72, cx + 118, cy + 72], fill=silver_hi)
        for ry in (-48, 0, 48):
            draw.line([(cx + 90, cy + ry), (cx + 164, cy + ry)], fill=gold, width=4)
        # Suspension ring on top
        draw.ellipse([cx + 115, cy - 126, cx + 139, cy - 102], outline=gold, width=4)

    return img


def _save_pil_image(image_field, filename: str, img: Image.Image) -> None:
    """Save a Pillow image cleanly into an ImageField, replacing any previous file with same path."""
    target_dir = Path(settings.MEDIA_ROOT) / image_field.field.upload_to
    target_dir.mkdir(parents=True, exist_ok=True)
    existing = target_dir / filename
    if existing.exists():
        existing.unlink()

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=90)
    image_field.save(filename, ContentFile(buf.getvalue()), save=False)


class Command(BaseCommand):
    help = 'ایجاد دسته‌بندی‌ها، محصولات، مشخصات فنی و تصاویر نمونه گالری جواهرات و حرز اصیل'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='پاک‌سازی داده‌های قبلی فروشگاه پیش از درج داده‌های نمونه',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            ProductImage.objects.all().delete()
            ProductSpecification.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING('داده‌های قبلی فروشگاه پاک‌سازی شد.'))

        categories_data = [
            {
                'title': 'انگشتر مردانه نقره',
                'slug': 'انگشتر-مردانه-نقره',
                'description': 'رکاب‌های دست‌ساز صفوی، فیلی و قلم‌زنی عیار ۹۲۵ مزین به عقیق یمنی، فیروزه نیشابور و دُرّ نجف.',
                'palette': ((245, 240, 230), (225, 214, 194)),
                'stone': ((158, 42, 43), (235, 145, 132)),
                'kind': 'ring',
            },
            {
                'title': 'انگشتر زنانه',
                'slug': 'انگشتر-زنانه',
                'description': 'طراحی‌های ظریف و اصیل زنانه با نگین‌های زمرد، یاقوت، فیروزه عجمی و آمتیست در رکاب نقره آبکاری رودیوم.',
                'palette': ((247, 241, 236), (231, 216, 206)),
                'stone': ((20, 107, 71), (138, 224, 182)),
                'kind': 'ring',
            },
            {
                'title': 'حرز و بازوبند',
                'slug': 'حرز-و-بازوبند',
                'description': 'نگارش اصیل حرز امام جواد (ع)، ابی‌دجانه و شرف‌الشمس روی پوست آهو با قاب نقره استوانه‌ای و بازوبند چرم گاوی.',
                'palette': ((15, 61, 62), (9, 38, 39)),
                'stone': ((86, 48, 30), (15, 61, 62)),
                'kind': 'hirz',
            },
            {
                'title': 'سنگ‌های معدنی اصیل',
                'slug': 'سنگ-های-معدنی-اصیل',
                'description': 'کلکسیون سنگ‌های نادر و معدنی طبیعی شامل شجر قائنات، زبرجد، باباقوری سه‌پوست و سلیمانی با شناسنامه اصالت.',
                'palette': ((242, 238, 228), (218, 210, 191)),
                'stone': ((30, 150, 168), (156, 234, 242)),
                'kind': 'ring',
            },
        ]

        categories_by_slug = {}
        for idx, cdata in enumerate(categories_data):
            category, _ = Category.objects.update_or_create(
                slug=cdata['slug'],
                defaults={
                    'title': cdata['title'],
                    'description': cdata['description'],
                },
            )
            bg_top, bg_bot = cdata['palette']
            canvas = _create_luxury_background(800, 500, bg_top, bg_bot)
            if cdata['kind'] == 'ring':
                _draw_ring_illustration(canvas, cdata['stone'][0], cdata['stone'][1], style_idx=idx)
            else:
                _draw_hirz_illustration(canvas, cdata['stone'][0], cdata['stone'][1], style_idx=0)
            _save_pil_image(category.image, f'cat-{idx + 1}.jpg', canvas)
            category.save()
            categories_by_slug[category.slug] = category

        products_data = [
            # --- Category 1: انگشتر مردانه نقره ---
            {
                'title': 'انگشتر عقیق سرخ یمنی رکاب صفوی',
                'slug': 'انگشتر-عقیق-سرخ-یمنی-رکاب-صفوی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-101',
                'price': 3450000,
                'discount_price': 2950000,
                'stock': 6,
                'is_featured': True,
                'short_description': 'عقیق سرخ کبدی اصل یمن با تراش دامله و رکاب تمام دست‌ساز طرح صفوی قلم‌زنی‌شده از نقره ۹۲۵.',
                'full_description': (
                    'این اثر فاخر ترکیبی از نگین عقیق سرخ طبیعی معدن یمن با طیف رنگی کبدی و رکاب دست‌ساز صفوی است.\n\n'
                    'تراش دامله نگین باعث بازتاب گرم و عمیق نور در سنگ شده و شانه‌های رکاب توسط استادکار قلم‌زنی اصفهان با نقوش اسلیمی مزین گردیده‌اند. '
                    'در روایات اسلامی، به‌دست کردن عقیق سرخ یمنی موجب آرامش قلب، برکت و ایمنی دانسته شده است.'
                ),
                'stone': ((158, 36, 38), (240, 145, 130)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار خالص دست‌ساز'),
                    ('نوع سنگ', 'عقیق سرخ کبدی طبیعی یمن'),
                    ('طرح و قلم‌زنی', 'رکاب صفوی با حاشیه اسلیمی دستی'),
                    ('وزن تقریبی', '۱۶٫۴ گرم'),
                    ('تضمین اصالت', 'همراه با شناسنامه فنی و ضمانت‌نامه کتبی'),
                ],
            },
            {
                'title': 'انگشتر فیروزه نیشابور شجری قلم‌زنی',
                'slug': 'انگشتر-فیروزه-نیشابور-شجری-قلم-زنی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-102',
                'price': 4200000,
                'discount_price': 3680000,
                'stock': 4,
                'is_featured': True,
                'short_description': 'فیروزه آبی آسمانی معدن نیشابور با رگه‌های شجری طبیعی روی رکاب نقره ۹۲۵ دست‌ساز.',
                'full_description': (
                    'نگین این انگشتر از بهترین رگه‌های فیروزه شجری معدن نیشابور انتخاب شده و بدون هیچ‌گونه رنگ‌شدگی یا رزین مصنوعی است.\n\n'
                    'رکاب محکم و خوش‌دست از نقره عیار ۹۲۵ با پرداخت مات و براق ساخته شده تا زیبایی رگه‌های طلایی-قهوه‌ای شجر در پس‌زمینه آبی فیروزه‌ای دوچندان شود.'
                ),
                'stone': ((24, 152, 174), (165, 238, 245)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'فیروزه شجری اصل معدن نیشابور'),
                    ('رنگ سنگ', 'آبی آسمانی با رگه‌های معدنی طبیعی'),
                    ('وزن تقریبی', '۱۴٫۸ گرم'),
                    ('نحوه نگهداری', 'دور از مواد شوینده، عطر و چربی نگهداری شود'),
                ],
            },
            {
                'title': 'انگشتر در نجف خطی رکاب اشکی',
                'slug': 'انگشتر-در-نجف-خطی-رکاب-اشکی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-103',
                'price': 2650000,
                'discount_price': None,
                'stock': 7,
                'is_featured': True,
                'short_description': 'سنگ در نجف شفاف با رگه‌های مویی طبیعی (در خطی) در رکاب کلاسیک اشکی نقره ۹۲۵.',
                'full_description': (
                    'در نجف خطی از محبوب‌ترین و اصیل‌ترین نگین‌های سرزمین نجف اشرف است که به‌واسطه رگه‌های سوزنی طبیعی درون بلور کوارتز شفاف شناخته می‌شود.\n\n'
                    'زیر نگین کاملاً باز طراحی شده تا نور به‌خوبی از دل بلور عبور کند و جلوه مویی آن نمایان بماند.'
                ),
                'stone': ((208, 218, 226), (255, 255, 255)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار با آبکاری مقاوم'),
                    ('نوع سنگ', 'در نجف خطی (کوارتز طبیعی نجف اشرف)'),
                    ('مدل رکاب', 'اشکی تمام‌دست با پشت باز'),
                    ('وزن تقریبی', '۱۲٫۵ گرم'),
                ],
            },
            {
                'title': 'انگشتر حدید صینی هفت‌جلاله حکاکی دستی',
                'slug': 'انگشتر-حدید-صینی-هفت-جلاله',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-104',
                'price': 2180000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'سنگ حدید معدنی اصیل با حکاکی دستی آیات شریفه هفت‌جلاله و رکاب ناودانی سنگین.',
                'full_description': (
                    'حکاکی عمیق و ظریف شرف‌الشمس و آیات هفت‌جلاله روی سنگ حدید صینی معدنی توسط حکاکی سنتی بدون استفاده از لیزر انجام گرفته است.\n\n'
                    'سنگ حدید وزن بالایی داشته و سطح آینه‌ای دودی آن جلوه‌ای باشکوه در کنار نقره براق ایجاد می‌کند.'
                ),
                'stone': ((64, 68, 74), (168, 174, 182)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار طرح ناودانی'),
                    ('نوع سنگ', 'حدید صینی معدنی (هماتیت طبیعی)'),
                    ('نوع حکاکی', 'دستی با قلم الماس، دعای هفت‌جلاله'),
                    ('وزن تقریبی', '۱۸٫۰ گرم'),
                ],
            },
            {
                'title': 'انگشتر یاقوت کبود آفریقایی رکاب فیلی',
                'slug': 'انگشتر-یاقوت-کبود-رکاب-فیلی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-105',
                'price': 5800000,
                'discount_price': 4990000,
                'stock': 2,
                'is_featured': False,
                'short_description': 'نگین یاقوت کبود معدنی با تراش فست جواهری بر روی رکاب پرهیبت فیلی نقره عیار ۹۲۵.',
                'full_description': (
                    'یاقوت کبود طبیعی با رنگ آبی سرمه‌ای عمیق و برش چندوجهی جواهری در قاب هشت‌چنگ قرار گرفته است.\n\n'
                    'رکاب فیلی توپر با تعادل وزنی مناسب برای استفاده روزمره و مجالس رسمی طراحی و پرداخت شده است.'
                ),
                'stone': ((29, 62, 138), (125, 168, 240)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار توپر'),
                    ('نوع سنگ', 'یاقوت کبود معدنی (سافایر طبیعی)'),
                    ('نوع تراش', 'فست چندوجهی جواهری'),
                    ('وزن تقریبی', '۱۷٫۲ گرم'),
                ],
            },
            # --- Category 2: انگشتر زنانه ---
            {
                'title': 'انگشتر زنانه زمرد پنجشیر رکاب ظریف',
                'slug': 'انگشتر-زنانه-زمرد-پنجشیر',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-201',
                'price': 4850000,
                'discount_price': 4250000,
                'stock': 4,
                'is_featured': True,
                'short_description': 'زمرد طبیعی پنجشیر با رنگ سبز مخملی و رکاب ظریف نقره ۹۲۵ با آبکاری طلا سفید.',
                'full_description': (
                    'زمرد پنجشیر به شفافیت و رنگ سبز زنده شهرت جهانی دارد. در این انگشتر زنانه، نگین با تراش باگت زمردی در پایه چهارچنگ ظریف نصب شده است.\n\n'
                    'آبکاری رودیوم (طلا سفید) روی نقره ۹۲۵ علاوه بر جلوگیری از تغییر رنگ، درخشندگی هم‌تراز با جواهرات لوکس می‌بخشد.'
                ),
                'stone': ((20, 110, 72), (132, 222, 178)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ با آبکاری رودیوم (ضدحساسیت)'),
                    ('نوع سنگ', 'زمرد طبیعی پنجشیر'),
                    ('سبک طراحی', 'ظریف جواهری چهارچنگ'),
                    ('وزن تقریبی', '۵٫۶ گرم'),
                ],
            },
            {
                'title': 'انگشتر زنانه یاقوت سرخ برمه طرح تاج',
                'slug': 'انگشتر-زنانه-یاقوت-سرخ-طرح-تاج',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-202',
                'price': 3200000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'یاقوت سرخ طبیعی با درخشش اناری و هاله‌ای از نگین‌های زیرکونیای تراش برلیان.',
                'full_description': (
                    'طراحی کلاسیک و اشرافی این انگشتر زنانه بر پایه سنگ یاقوت سرخ طبیعی در مرکز و مخراج‌کاری ظریف نگین‌های جانبی شکل گرفته است.\n\n'
                    'مناسب برای هدیه و استفاده در مهمانی‌ها با ماندگاری بالای رنگ و جلای فلز.'
                ),
                'stone': ((164, 28, 58), (242, 138, 162)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ آبکاری‌شده'),
                    ('نوع سنگ', 'یاقوت سرخ معدنی'),
                    ('نگین جانبی', 'مخراج‌کاری زیرکونیای سوئیسی'),
                    ('وزن تقریبی', '۴٫۹ گرم'),
                ],
            },
            {
                'title': 'انگشتر زنانه فیروزه عجمی نیشابور طرح اشک',
                'slug': 'انگشتر-زنانه-فیروزه-عجمی-طرح-اشک',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-203',
                'price': 2490000,
                'discount_price': None,
                'stock': 8,
                'is_featured': True,
                'short_description': 'فیروزه عجمی یکدست و بدون رگه نیشابور با قاب نقره ظریف و قلم‌زنی لبه.',
                'full_description': (
                    'فیروزه عجمی با رنگ آبی خالص و سطح صاف آینه‌ای، زیباترین جلوه را در رکاب‌های زنانه می‌آفریند.\n\n'
                    'دور قاب با ظرافت تمام دندانه‌کاری شده تا جلوه‌ای اصیل و ایرانی به دستان شما ببخشد.'
                ),
                'stone': ((28, 165, 184), (174, 240, 248)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'فیروزه عجمی صاف نیشابور'),
                    ('فرم نگین', 'اشک دامله'),
                    ('وزن تقریبی', '۵٫۲ گرم'),
                ],
            },
            {
                'title': 'انگشتر زنانه عقیق شفت‌العبد تراش بیضی',
                'slug': 'انگشتر-زنانه-عقیق-شفت-العبد',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-204',
                'price': 1980000,
                'discount_price': 1690000,
                'stock': 6,
                'is_featured': False,
                'short_description': 'عقیق سرخ تیره شفت‌العبد با تراش ظریف بیضی و رکاب دو بازو.',
                'full_description': (
                    'انتخابی سبک، خوش‌استایل و پرانرژی برای علاقه‌مندان به سنگ‌های اصیل اسلامی. '
                    'رکاب دو بازوی نقره ۹۲۵ جلوه‌ای مدرن و در عین حال سنتی به این سنگ ارزشمند داده است.'
                ),
                'stone': ((126, 26, 36), (222, 128, 132)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'عقیق شفت‌العبد طبیعی'),
                    ('وزن تقریبی', '۴٫۳ گرم'),
                ],
            },
            {
                'title': 'انگشتر زنانه آمتیست بنفش رکاب شبکه',
                'slug': 'انگشتر-زنانه-آمتیست-بنفش',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-205',
                'price': 2350000,
                'discount_price': None,
                'stock': 0,
                'is_featured': False,
                'short_description': 'یاقوت ارغوانی (آمتیست) طبیعی با تراش دامله و رکاب شبکه‌کاری سنتی.',
                'full_description': (
                    'آمتیست طبیعی با طیف بنفش سلطنتی و شفافیت بالا که از دیرباز نماد آرامش ذهن و وقار بوده است.\n\n'
                    'این اثر در حال حاضر به اتمام رسیده و در نوبت تولید کارگاهی قرار دارد.'
                ),
                'stone': ((111, 60, 140), (206, 168, 232)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار شبکه‌کاری'),
                    ('نوع سنگ', 'آمتیست طبیعی (کوارتز بنفش)'),
                    ('وزن تقریبی', '۶٫۱ گرم'),
                ],
            },
            # --- Category 3: حرز و بازوبند ---
            {
                'title': 'حرز امام جواد (ع) دست‌نویس روی پوست آهو با بازوبند چرمی',
                'slug': 'حرز-امام-جواد-دست-نویس-پوست-آهو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-301',
                'price': 1850000,
                'discount_price': 1590000,
                'stock': 12,
                'is_featured': True,
                'short_description': 'کتابت دقیق حرز کبیر و صغیر امام جواد (ع) با قلم و جوهر زعفران روی پوست آهو همراه با بازوبند چرم گاوی دست‌دوز.',
                'full_description': (
                    'این حرز مبارک مطابق نسخه معتبر کتاب «مهج‌الدعوات» سید بن طاووس، پس از رعایت غسل، طهارت، رو به قبله و در ساعات سعد قمر در عقرب‌نبوده، '
                    'با جوهر زعفران و گلاب روی پوست آهوی دباغی‌شده دست‌نویس شده است.\n\n'
                    'شما می‌توانید محفظه نگهداری را از میان قاب نقره استوانه‌ای عیار ۹۲۵، بازوبند چرمی دست‌دوز یا نسخه لول‌شده انتخاب نمایید. '
                    'آداب بستن و دعای همراه حرز به‌صورت چاپی و تاییدشده در بسته ارسال می‌شود.'
                ),
                'stone': ((88, 52, 34), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس کامل با قلم نی و جوهر زعفران روی پوست آهو'),
                    ('جنس محفظه', 'قابل انتخاب: نقره ۹۲۵ / چرم طبیعی گاوی / لول‌شده'),
                    ('متن حرز', 'حرز کبیر امام جواد (ع) طبق سند مهج‌الدعوات'),
                    ('آداب شرعی', 'دارای گواهی رعایت طهارت، ساعت سعد و نماز حرز'),
                    ('اقلام همراه', 'دفترچه راهنمای آداب بستن و نگهداری'),
                ],
            },
            {
                'title': 'حرز ابی‌دجانه با قاب نقره استوانه‌ای قلم‌زنی',
                'slug': 'حرز-ابی-دجانه-قاب-نقره',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-302',
                'price': 2450000,
                'discount_price': None,
                'stock': 7,
                'is_featured': True,
                'short_description': 'حرز شریف ابی‌دجانه انصاری تحریر‌شده روی پوست آهو در محفظه استوانه‌ای نقره ۹۲۵ ضدآب و قلم‌زنی‌شده.',
                'full_description': (
                    'حرز ابی‌دجانه از ادعیه مأثور و مجرب جهت ایمنی منزل، آرامش خانواده و دفع چشم‌زخم و آفات است.\n\n'
                    'لوله نقره ۹۲۵ با درپوش رزوه‌دار محکم و آب‌بندی کامل طراحی شده تا پوست آهو در طول سالیان متمادی از رطوبت محفوظ بماند.'
                ),
                'stone': ((74, 44, 28), (200, 169, 106)),
                'style_idx': 1,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس سنتی روی پوست آهو'),
                    ('جنس محفظه', 'نقره ۹۲۵ عیار قلم‌زنی‌شده با درپوش رزوه‌ای'),
                    ('طول محفظه', '۴٫۸ سانتی‌متر استاندارد'),
                    ('وزن قاب نقره', '۱۱٫۲ گرم'),
                    ('امکان آویز', 'دارای دو حلقه جهت استفاده به عنوان بازوبند یا گردن‌آویز'),
                ],
            },
            {
                'title': 'حرز کبیر امام جواد (ع) قاب نقره دوقلو و بازوبند گاوی',
                'slug': 'حرز-کبیر-قاب-نقره-دوقلو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-303',
                'price': 2850000,
                'discount_price': 2480000,
                'stock': 5,
                'is_featured': False,
                'short_description': 'مجموعه کامل حرز کبیر و صغیر درون لوله نقره قلم‌زنی با بازوبند چرم طبیعی دست‌دوز و سگک برنجی.',
                'full_description': (
                    'این مجموعه پکیج کامل برای بستن حرز بر بازوی راست مطابق سفارش علما است. '
                    'بند چرمی از چرم گاوی گیاهی دباغی شده که با پوست بدن کاملاً سازگار بوده و ایجاد حساسیت نمی‌کند.'
                ),
                'stone': ((62, 38, 26), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس روی پوست آهو (حرز کبیر + صغیر)'),
                    ('جنس محفظه', 'نقره ۹۲۵ عیار و بند چرم طبیعی دست‌دوز'),
                    ('قابلیت تنظیم', 'بند چرمی قابل تنظیم برای تمام سایزهای بازو'),
                    ('گواهی اصالت', 'ممهور به مهر کاتب و گواهی نگارش'),
                ],
            },
            {
                'title': 'حرز شرف‌الشمس اصیل نوزدهم فروردین با محفظه نقره',
                'slug': 'حرز-شرف-الشمس-پوست-آهو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-304',
                'price': 1920000,
                'discount_price': None,
                'stock': 9,
                'is_featured': False,
                'short_description': 'لوح کامل شرف‌الشمس و اسماء حسنی تحریرشده در روز ۱۹ فروردین روی پوست آهو با محفظه نقره.',
                'full_description': (
                    'تألیف شرف‌الشمس شامل نقش خاتم نبوت، حروف مقطعه و ادعیه مأثوره که در ساعت شرف خورشید نوزدهم فروردین با مرکب زعفران بر پوست آهو نگاشته شده است.'
                ),
                'stone': ((98, 62, 34), (168, 126, 48)),
                'style_idx': 1,
                'specs': [
                    ('نوع نگارش', 'تحریر در ساعت شرف نوزدهم فروردین روی پوست آهو'),
                    ('جنس محفظه', 'نقره ۹۲۵ / بند چرمی دست‌دوز'),
                    ('ابعاد رول', 'بسته استوانه‌ای جمع‌وجور ۴ سانتی‌متری'),
                ],
            },
            {
                'title': 'بازوبند حرز صغیر و دعای عهد دست‌نویس با جلد چرمی',
                'slug': 'بازوبند-حرز-صغیر-جلد-چرمی',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-305',
                'price': 1180000,
                'discount_price': None,
                'stock': 10,
                'is_featured': False,
                'short_description': 'نسخه سبک و روزمره حرز صغیر امام جواد (ع) در غلاف چرمی دست‌دوز قابل بستن روی بازو یا قرارگیری در کیف.',
                'full_description': (
                    'طراحی‌شده برای افرادی که به دنبال حرز سبک و راحت برای استفاده مداوم هستند. '
                    'پوست آهو پس از نگارش در لایه محافظ قرار گرفته و داخل بازوبند چرمی دوخته شده است.'
                ),
                'stone': ((104, 68, 44), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس حرز صغیر روی پوست آهو'),
                    ('جنس محفظه', 'چرم طبیعی گاوی دست‌دوز / قاب نقره انتخابی'),
                    ('وزن کل', '۱۸ گرم بسیار سبک'),
                ],
            },
            # --- Category 4: سنگ‌های معدنی اصیل ---
            {
                'title': 'انگشتر شجر پاییزی قائنات کلکسیونی رکاب دست‌ساز',
                'slug': 'انگشتر-شجر-پاییزی-قائنات',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-401',
                'price': 3750000,
                'discount_price': 3290000,
                'stock': 3,
                'is_featured': True,
                'short_description': 'عقیق شجر طبیعی قائنات با نقش درختان پاییزی واضح و تکرارناپذیر در رکاب نقره ۹۲۵.',
                'full_description': (
                    'در دل این سنگ معدنی اصیل از منطقه قائنات خراسان، رسوبات منگنز و آهن طی میلیون‌ها سال منظره طبیعی درختان پاییزی را نقش بسته‌اند.\n\n'
                    'هر سنگ شجر در دنیا کاملاً منحصربه‌فرد است و هیچ نسخه مشابهی از آن وجود ندارد.'
                ),
                'stone': ((158, 108, 62), (234, 198, 152)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار دست‌ساز'),
                    ('نوع سنگ', 'عقیق شجر پاییزی طبیعی قائنات'),
                    ('ویژگی شاخص', 'منظره طبیعی تک‌نسخه بدون هیچ بهسازی'),
                    ('وزن تقریبی', '۱۵٫۹ گرم'),
                ],
            },
            {
                'title': 'انگشتر زبرجد سبز معدنی تراش فست رکاب ناودانی',
                'slug': 'انگشتر-زبرجد-سبز-معدنی',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-402',
                'price': 3900000,
                'discount_price': None,
                'stock': 4,
                'is_featured': False,
                'short_description': 'سنگ زبرجد طبیعی (پریدوت) با شفافیت کریستالی سبز زیتونی در رکاب نقره ۹۲۵.',
                'full_description': (
                    'زبرجد سبز معدنی از سنگ‌های قیمتی با طیف سبز طلایی زنده است که زیر نور روز درخشش استثنایی دارد.\n\n'
                    'در کتب جواهرشناسی قدیم، زبرجد به‌عنوان سنگ گشایش روزی و رفع اندوه معرفی شده است.'
                ),
                'stone': ((107, 158, 56), (194, 232, 134)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'زبرجد معدنی طبیعی (Peridot)'),
                    ('نوع تراش', 'فست مستطیلی درخشان'),
                    ('وزن تقریبی', '۱۳٫۲ گرم'),
                ],
            },
            {
                'title': 'انگشتر عقیق سلیمانی چشم‌دار طبیعی',
                'slug': 'انگشتر-عقیق-سلیمانی-چشم-دار',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-403',
                'price': 2750000,
                'discount_price': None,
                'stock': 6,
                'is_featured': False,
                'short_description': 'عقیق سلیمانی با دایره‌های متحدالمرکز طبیعی (چشم سلیمانی) و رکاب نقره دست‌ساز.',
                'full_description': (
                    'عقیق سلیمانی با خطوط طبیعی لایه‌لایه و مرکز متقارن، از سنگ‌های کلکسیونی مورد توجه علاقه‌مندان به احجار کریمه است.\n\n'
                    'رکاب نقره با لبه‌های چنگ‌دار محکم، محافظت کامل از حاشیه سنگ را تضمین می‌کند.'
                ),
                'stone': ((86, 68, 62), (198, 174, 162)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'عقیق سلیمانی معدنی طبیعی'),
                    ('وزن تقریبی', '۱۴٫۵ گرم'),
                ],
            },
            {
                'title': 'انگشتر باباقوری سه‌پوست یمنی اصیل',
                'slug': 'انگشتر-باباقوری-سه-پوست-یمنی',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-404',
                'price': 3150000,
                'discount_price': 2690000,
                'stock': 2,
                'is_featured': False,
                'short_description': 'سنگ باباقوری سه‌پوست طبیعی با تضاد رنگی چشم‌نواز مشکی و سفید و رکاب شیرازی.',
                'full_description': (
                    'باباقوری سه‌پوست اصیل از خانواده جزع یمانی است که لایه‌های سفید و سیاه آن با برش دامله به‌صورت کامل تفکیک شده‌اند.\n\n'
                    'این سنگ در فرهنگ ایرانی و عربی به دفع نظر بد شهرت دارد.'
                ),
                'stone': ((42, 42, 46), (225, 225, 230)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ طرح شیرازی'),
                    ('نوع سنگ', 'جزع سه‌پوست طبیعی (باباقوری)'),
                    ('وزن تقریبی', '۱۵٫۱ گرم'),
                ],
            },
            {
                'title': 'انگشتر توپاز آبی لندن با رکاب نقره ۹۲۵',
                'slug': 'انگشتر-توپاز-آبی-لندن',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-405',
                'price': 3400000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'نگین توپاز آبی عمیق (London Blue) با تلألو خیره‌کننده روی رکاب خوش‌تراش نقره.',
                'full_description': (
                    'توپاز آبی با شفافیت بسیار بالا و سختی ۸ موس، انتخابی ماندگار و مقاوم برای استفاده همیشگی در کنار استایل‌های کلاسیک و رسمی است.'
                ),
                'stone': ((22, 92, 134), (144, 212, 245)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار'),
                    ('نوع سنگ', 'توپاز آبی لندن طبیعی'),
                    ('سختی سنگ', '۸ در مقیاس موس'),
                    ('وزن تقریبی', '۱۳٫۹ گرم'),
                ],
            },
        ]

        gallery_themes = [
            ('نمایه استودیویی روی مخمل زمردی', (15, 61, 62), (9, 36, 37)),
            ('نمایه کارگاهی با گواهی اصالت', (243, 238, 228), (224, 214, 194)),
        ]

        for idx, pdata in enumerate(products_data, start=1):
            category = categories_by_slug[pdata['category']]
            product, _ = Product.objects.update_or_create(
                sku=pdata['sku'],
                defaults={
                    'title': pdata['title'],
                    'slug': pdata['slug'],
                    'category': category,
                    'product_type': pdata['product_type'],
                    'price': pdata['price'],
                    'discount_price': pdata['discount_price'],
                    'stock': pdata['stock'],
                    'short_description': pdata['short_description'],
                    'full_description': pdata['full_description'],
                    'is_featured': pdata['is_featured'],
                },
            )

            # Main image on warm ivory luxury studio backdrop
            main_canvas = _create_luxury_background(800, 600, (250, 248, 245), (235, 228, 214))
            if product.product_type == Product.ProductType.RING:
                _draw_ring_illustration(main_canvas, pdata['stone'][0], pdata['stone'][1], style_idx=pdata['style_idx'])
            else:
                _draw_hirz_illustration(main_canvas, pdata['stone'][0], pdata['stone'][1], style_idx=pdata['style_idx'])
            _save_pil_image(product.main_image, f'{product.sku.lower()}-main.jpg', main_canvas)
            product.save()

            # Replace gallery images cleanly
            product.images.all().delete()
            for g_idx, (alt_label, g_top, g_bot) in enumerate(gallery_themes, start=1):
                g_img = ProductImage(product=product, alt_text=f'{product.title} — {alt_label}')
                g_canvas = _create_luxury_background(800, 600, g_top, g_bot)
                if product.product_type == Product.ProductType.RING:
                    _draw_ring_illustration(
                        g_canvas,
                        pdata['stone'][0],
                        pdata['stone'][1],
                        style_idx=pdata['style_idx'] + g_idx,
                    )
                else:
                    _draw_hirz_illustration(
                        g_canvas,
                        pdata['stone'][0],
                        pdata['stone'][1],
                        style_idx=pdata['style_idx'] + g_idx,
                    )
                _save_pil_image(g_img.image, f'{product.sku.lower()}-gallery-{g_idx}.jpg', g_canvas)
                g_img.save()

            # Replace technical specifications cleanly
            product.specifications.all().delete()
            ProductSpecification.objects.bulk_create(
                [
                    ProductSpecification(product=product, key=k, value=v)
                    for k, v in pdata['specs']
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'عملیات با موفقیت انجام شد: {len(categories_data)} دسته‌بندی و {len(products_data)} محصول همراه با تصاویر و مشخصات فنی ذخیره شدند.'
            )
        )
