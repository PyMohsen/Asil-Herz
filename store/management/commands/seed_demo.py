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
                'title_en': "Men's Silver Rings",
                'slug': 'انگشتر-مردانه-نقره',
                'description': 'رکاب‌های دست‌ساز صفوی، فیلی و قلم‌زنی عیار ۹۲۵ مزین به عقیق یمنی، فیروزه نیشابور و دُرّ نجف.',
                'description_en': 'Handcrafted 925 sterling silver bands in Safavid, Fili, and hand-engraved styles set with Yemeni agate, Nishapur turquoise, and Durr-e Najaf.',
                'palette': ((245, 240, 230), (225, 214, 194)),
                'stone': ((158, 42, 43), (235, 145, 132)),
                'kind': 'ring',
            },
            {
                'title': 'انگشتر زنانه',
                'title_en': "Women's Rings",
                'slug': 'انگشتر-زنانه',
                'description': 'طراحی‌های ظریف و اصیل زنانه با نگین‌های زمرد، یاقوت، فیروزه عجمی و آمتیست در رکاب نقره آبکاری رودیوم.',
                'description_en': "Refined and authentic women's silver ring designs set with emerald, ruby, Ajami turquoise, and amethyst in rhodium-plated 925 silver.",
                'palette': ((247, 241, 236), (231, 216, 206)),
                'stone': ((20, 107, 71), (138, 224, 182)),
                'kind': 'ring',
            },
            {
                'title': 'حرز و بازوبند',
                'title_en': 'Hirz & Leather Armlets',
                'slug': 'حرز-و-بازوبند',
                'description': 'نگارش اصیل حرز امام جواد (ع)، ابی‌دجانه و شرف‌الشمس روی پوست آهو با قاب نقره استوانه‌ای و بازوبند چرم گاوی.',
                'description_en': 'Authentic scribal Hirz of Imam Jawad (AS), Abi Dujana, and Sharaf-ol-Shams written on deerskin parchment with cylindrical silver cases and cowhide armlets.',
                'palette': ((15, 61, 62), (9, 38, 39)),
                'stone': ((86, 48, 30), (15, 61, 62)),
                'kind': 'hirz',
            },
            {
                'title': 'سنگ‌های معدنی اصیل',
                'title_en': 'Authentic Mineral Gemstones',
                'slug': 'سنگ-های-معدنی-اصیل',
                'description': 'کلکسیون سنگ‌های نادر و معدنی طبیعی شامل شجر قائنات، زبرجد، باباقوری سه‌پوست و سلیمانی با شناسنامه اصالت.',
                'description_en': 'A rare collection of natural mineral gemstones including Qaenat scenic agate, peridot, three-layer Babaghori onyx, and Suleimani agate with authenticity certificate.',
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
                    'title_en': cdata['title_en'],
                    'description': cdata['description'],
                    'description_en': cdata['description_en'],
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
                'title_en': 'Yemeni Red Agate Ring — Safavid Silver Band',
                'slug': 'انگشتر-عقیق-سرخ-یمنی-رکاب-صفوی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-101',
                'price': 3450000,
                'discount_price': 2950000,
                'stock': 6,
                'is_featured': True,
                'short_description': 'عقیق سرخ کبدی اصل یمن با تراش دامله و رکاب تمام دست‌ساز طرح صفوی قلم‌زنی‌شده از نقره ۹۲۵.',
                'short_description_en': 'Authentic deep-red Yemeni cabochon agate mounted in a fully handcrafted, engraved Safavid-style 925 sterling silver band.',
                'full_description': (
                    'این اثر فاخر ترکیبی از نگین عقیق سرخ طبیعی معدن یمن با طیف رنگی کبدی و رکاب دست‌ساز صفوی است.\n\n'
                    'تراش دامله نگین باعث بازتاب گرم و عمیق نور در سنگ شده و شانه‌های رکاب توسط استادکار قلم‌زنی اصفهان با نقوش اسلیمی مزین گردیده‌اند. '
                    'در روایات اسلامی، به‌دست کردن عقیق سرخ یمنی موجب آرامش قلب، برکت و ایمنی دانسته شده است.'
                ),
                'full_description_en': (
                    'This distinguished piece pairs a natural deep-crimson agate mined in Yemen with an artisan-forged Safavid silver setting.\n\n'
                    'Its smooth cabochon dome captures a warm, rich glow while the shoulders are hand-engraved by Isfahani master artisans with traditional arabesque motifs. '
                    'In classical Islamic tradition, wearing genuine Yemeni red agate is cherished for serenity, blessing, and spiritual protection.'
                ),
                'stone': ((158, 36, 38), (240, 145, 130)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار خالص دست‌ساز', 'Band Material', 'Handcrafted pure 925 sterling silver'),
                    ('نوع سنگ', 'عقیق سرخ کبدی طبیعی یمن', 'Gemstone Type', 'Natural deep-red Yemeni agate'),
                    ('طرح و قلم‌زنی', 'رکاب صفوی با حاشیه اسلیمی دستی', 'Design & Engraving', 'Safavid band with hand-engraved arabesque borders'),
                    ('وزن تقریبی', '۱۶٫۴ گرم', 'Approx. Weight', '16.4 g'),
                    ('تضمین اصالت', 'همراه با شناسنامه فنی و ضمانت‌نامه کتبی', 'Authenticity Guarantee', 'Includes gemological card and written warranty'),
                ],
            },
            {
                'title': 'انگشتر فیروزه نیشابور شجری قلم‌زنی',
                'title_en': 'Nishapur Dendritic Turquoise Ring — Hand-Engraved',
                'slug': 'انگشتر-فیروزه-نیشابور-شجری-قلم-زنی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-102',
                'price': 4200000,
                'discount_price': 3680000,
                'stock': 4,
                'is_featured': True,
                'short_description': 'فیروزه آبی آسمانی معدن نیشابور با رگه‌های شجری طبیعی روی رکاب نقره ۹۲۵ دست‌ساز.',
                'short_description_en': 'Sky-blue Nishapur turquoise featuring natural dendritic matrix veins set in a handcrafted 925 silver ring.',
                'full_description': (
                    'نگین این انگشتر از بهترین رگه‌های فیروزه شجری معدن نیشابور انتخاب شده و بدون هیچ‌گونه رنگ‌شدگی یا رزین مصنوعی است.\n\n'
                    'رکاب محکم و خوش‌دست از نقره عیار ۹۲۵ با پرداخت مات و براق ساخته شده تا زیبایی رگه‌های طلایی-قهوه‌ای شجر در پس‌زمینه آبی فیروزه‌ای دوچندان شود.'
                ),
                'full_description_en': (
                    'Selected from prime veins of the historic Nishapur mines, this untreated turquoise displays vivid sky-blue hues free of dyes or synthetic stabilizers.\n\n'
                    'The ergonomic 925 sterling band combines satin and mirror finishes to highlight the natural golden-brown matrix flowing across the stone.'
                ),
                'stone': ((24, 152, 174), (165, 238, 245)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'فیروزه شجری اصل معدن نیشابور', 'Gemstone Type', 'Authentic Nishapur dendritic turquoise'),
                    ('رنگ سنگ', 'آبی آسمانی با رگه‌های معدنی طبیعی', 'Stone Color', 'Sky blue with natural mineral matrix'),
                    ('وزن تقریبی', '۱۴٫۸ گرم', 'Approx. Weight', '14.8 g'),
                    ('نحوه نگهداری', 'دور از مواد شوینده، عطر و چربی نگهداری شود', 'Care Instructions', 'Keep away from detergents, perfumes, and oils'),
                ],
            },
            {
                'title': 'انگشتر در نجف خطی رکاب اشکی',
                'title_en': 'Linear Durr-e Najaf Ring — Teardrop Band',
                'slug': 'انگشتر-در-نجف-خطی-رکاب-اشکی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-103',
                'price': 2650000,
                'discount_price': None,
                'stock': 7,
                'is_featured': True,
                'short_description': 'سنگ در نجف شفاف با رگه‌های مویی طبیعی (در خطی) در رکاب کلاسیک اشکی نقره ۹۲۵.',
                'short_description_en': 'Crystal-clear Durr-e Najaf quartz with delicate natural needle inclusions in a classic teardrop 925 silver setting.',
                'full_description': (
                    'در نجف خطی از محبوب‌ترین و اصیل‌ترین نگین‌های سرزمین نجف اشرف است که به‌واسطه رگه‌های سوزنی طبیعی درون بلور کوارتز شفاف شناخته می‌شود.\n\n'
                    'زیر نگین کاملاً باز طراحی شده تا نور به‌خوبی از دل بلور عبور کند و جلوه مویی آن نمایان بماند.'
                ),
                'full_description_en': (
                    'Linear Durr-e Najaf is among the most sought-after stones from Najaf Ashraf, celebrated for the fine hair-like natural rutile inclusions suspended within pure rock crystal.\n\n'
                    'Its open-back bezel allows full light transmission so every crystalline filament glistens clearly.'
                ),
                'stone': ((208, 218, 226), (255, 255, 255)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار با آبکاری مقاوم', 'Band Material', '925 sterling silver with durable plating'),
                    ('نوع سنگ', 'در نجف خطی (کوارتز طبیعی نجف اشرف)', 'Gemstone Type', 'Linear Durr-e Najaf (natural Najaf quartz)'),
                    ('مدل رکاب', 'اشکی تمام‌دست با پشت باز', 'Band Style', 'Handcrafted open-back teardrop'),
                    ('وزن تقریبی', '۱۲٫۵ گرم', 'Approx. Weight', '12.5 g'),
                ],
            },
            {
                'title': 'انگشتر حدید صینی هفت‌جلاله حکاکی دستی',
                'title_en': 'Hand-Engraved Hematite (Hadid Sini) Seven-Majesty Ring',
                'slug': 'انگشتر-حدید-صینی-هفت-جلاله',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-104',
                'price': 2180000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'سنگ حدید معدنی اصیل با حکاکی دستی آیات شریفه هفت‌جلاله و رکاب ناودانی سنگین.',
                'short_description_en': 'Authentic natural hematite gemstone featuring traditional hand-carved Seven-Majesty (Haft Jalalah) calligraphy in a heavy channel silver band.',
                'full_description': (
                    'حکاکی عمیق و ظریف شرف‌الشمس و آیات هفت‌جلاله روی سنگ حدید صینی معدنی توسط حکاکی سنتی بدون استفاده از لیزر انجام گرفته است.\n\n'
                    'سنگ حدید وزن بالایی داشته و سطح آینه‌ای دودی آن جلوه‌ای باشکوه در کنار نقره براق ایجاد می‌کند.'
                ),
                'full_description_en': (
                    'The sacred Haft Jalalah inscriptions and Sharaf-ol-Shams motifs are carved strictly by hand with diamond-tip chisels—never laser etched—into dense mineral hematite.\n\n'
                    'Its metallic charcoal luster contrasts impressively against the weighty polished sterling silver shank.'
                ),
                'stone': ((64, 68, 74), (168, 174, 182)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار طرح ناودانی', 'Band Material', 'Channel-style 925 sterling silver'),
                    ('نوع سنگ', 'حدید صینی معدنی (هماتیت طبیعی)', 'Gemstone Type', 'Natural mineral hematite (Hadid Sini)'),
                    ('نوع حکاکی', 'دستی با قلم الماس، دعای هفت‌جلاله', 'Engraving', 'Hand-carved diamond-tip Haft Jalalah script'),
                    ('وزن تقریبی', '۱۸٫۰ گرم', 'Approx. Weight', '18.0 g'),
                ],
            },
            {
                'title': 'انگشتر یاقوت کبود آفریقایی رکاب فیلی',
                'title_en': 'African Blue Sapphire Ring — Heavy Fili Band',
                'slug': 'انگشتر-یاقوت-کبود-رکاب-فیلی',
                'category': 'انگشتر-مردانه-نقره',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-105',
                'price': 5800000,
                'discount_price': 4990000,
                'stock': 2,
                'is_featured': False,
                'short_description': 'نگین یاقوت کبود معدنی با تراش فست جواهری بر روی رکاب پرهیبت فیلی نقره عیار ۹۲۵.',
                'short_description_en': 'Faceted natural African blue sapphire set into a bold, solid 925 silver Fili-style band.',
                'full_description': (
                    'یاقوت کبود طبیعی با رنگ آبی سرمه‌ای عمیق و برش چندوجهی جواهری در قاب هشت‌چنگ قرار گرفته است.\n\n'
                    'رکاب فیلی توپر با تعادل وزنی مناسب برای استفاده روزمره و مجالس رسمی طراحی و پرداخت شده است.'
                ),
                'full_description_en': (
                    'A deep midnight-blue natural sapphire precision-cut into brilliant jewelry facets rests securely inside an eight-prong crown bezel.\n\n'
                    'Crafted with a solid Fili shank offering comfortable weight distribution for both daily wear and formal occasions.'
                ),
                'stone': ((29, 62, 138), (125, 168, 240)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار توپر', 'Band Material', 'Solid 925 sterling silver'),
                    ('نوع سنگ', 'یاقوت کبود معدنی (سافایر طبیعی)', 'Gemstone Type', 'Natural mineral blue sapphire'),
                    ('نوع تراش', 'فست چندوجهی جواهری', 'Cut', 'Precision multi-faceted jewelry cut'),
                    ('وزن تقریبی', '۱۷٫۲ گرم', 'Approx. Weight', '17.2 g'),
                ],
            },
            # --- Category 2: انگشتر زنانه ---
            {
                'title': 'انگشتر زنانه زمرد پنجشیر رکاب ظریف',
                'title_en': "Women's Panjshir Emerald Ring — Delicate Band",
                'slug': 'انگشتر-زنانه-زمرد-پنجشیر',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-201',
                'price': 4850000,
                'discount_price': 4250000,
                'stock': 4,
                'is_featured': True,
                'short_description': 'زمرد طبیعی پنجشیر با رنگ سبز مخملی و رکاب ظریف نقره ۹۲۵ با آبکاری طلا سفید.',
                'short_description_en': 'Velvety-green natural Panjshir emerald held in a delicate rhodium-plated 925 sterling silver setting.',
                'full_description': (
                    'زمرد پنجشیر به شفافیت و رنگ سبز زنده شهرت جهانی دارد. در این انگشتر زنانه، نگین با تراش باگت زمردی در پایه چهارچنگ ظریف نصب شده است.\n\n'
                    'آبکاری رودیوم (طلا سفید) روی نقره ۹۲۵ علاوه بر جلوگیری از تغییر رنگ، درخشندگی هم‌تراز با جواهرات لوکس می‌بخشد.'
                ),
                'full_description_en': (
                    'Renowned worldwide for its vivid, saturated green hue, this natural Panjshir emerald features an emerald-cut step silhouette in a sleek four-prong mount.\n\n'
                    'Finished with hypoallergenic white-gold rhodium plating over 925 silver for enduring tarnish resistance and fine-jewelry brilliance.'
                ),
                'stone': ((20, 110, 72), (132, 222, 178)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ با آبکاری رودیوم (ضدحساسیت)', 'Band Material', '925 silver with hypoallergenic rhodium plating'),
                    ('نوع سنگ', 'زمرد طبیعی پنجشیر', 'Gemstone Type', 'Natural Panjshir emerald'),
                    ('سبک طراحی', 'ظریف جواهری چهارچنگ', 'Design Style', 'Delicate four-prong fine jewelry'),
                    ('وزن تقریبی', '۵٫۶ گرم', 'Approx. Weight', '5.6 g'),
                ],
            },
            {
                'title': 'انگشتر زنانه یاقوت سرخ برمه طرح تاج',
                'title_en': "Women's Burmese Red Ruby Ring — Crown Setting",
                'slug': 'انگشتر-زنانه-یاقوت-سرخ-طرح-تاج',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-202',
                'price': 3200000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'یاقوت سرخ طبیعی با درخشش اناری و هاله‌ای از نگین‌های زیرکونیای تراش برلیان.',
                'short_description_en': 'Natural pomegranate-red ruby encircled by a delicate halo of brilliant-cut cubic zirconia accents.',
                'full_description': (
                    'طراحی کلاسیک و اشرافی این انگشتر زنانه بر پایه سنگ یاقوت سرخ طبیعی در مرکز و مخراج‌کاری ظریف نگین‌های جانبی شکل گرفته است.\n\n'
                    'مناسب برای هدیه و استفاده در مهمانی‌ها با ماندگاری بالای رنگ و جلای فلز.'
                ),
                'full_description_en': (
                    'This regal classic centers on a vivid natural red ruby framed by micro-paved brilliant side stones.\n\n'
                    'An ideal piece for gifting and evening wear with lasting rhodium sheen and secure stone setting.'
                ),
                'stone': ((164, 28, 58), (242, 138, 162)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ آبکاری‌شده', 'Band Material', 'Plated 925 sterling silver'),
                    ('نوع سنگ', 'یاقوت سرخ معدنی', 'Gemstone Type', 'Natural mineral red ruby'),
                    ('نگین جانبی', 'مخراج‌کاری زیرکونیای سوئیسی', 'Accent Stones', 'Micro-set Swiss zirconia'),
                    ('وزن تقریبی', '۴٫۹ گرم', 'Approx. Weight', '4.9 g'),
                ],
            },
            {
                'title': 'انگشتر زنانه فیروزه عجمی نیشابور طرح اشک',
                'title_en': "Women's Nishapur Ajami Turquoise Ring — Teardrop Design",
                'slug': 'انگشتر-زنانه-فیروزه-عجمی-طرح-اشک',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-203',
                'price': 2490000,
                'discount_price': None,
                'stock': 8,
                'is_featured': True,
                'short_description': 'فیروزه عجمی یکدست و بدون رگه نیشابور با قاب نقره ظریف و قلم‌زنی لبه.',
                'short_description_en': 'Pure, matrix-free Nishapur Ajami turquoise set in a finely beaded teardrop 925 silver bezel.',
                'full_description': (
                    'فیروزه عجمی با رنگ آبی خالص و سطح صاف آینه‌ای، زیباترین جلوه را در رکاب‌های زنانه می‌آفریند.\n\n'
                    'دور قاب با ظرافت تمام دندانه‌کاری شده تا جلوه‌ای اصیل و ایرانی به دستان شما ببخشد.'
                ),
                'full_description_en': (
                    'Prized for its pure, uniform Persian blue color without dark matrix lines, Ajami turquoise brings timeless elegance to feminine silvercraft.\n\n'
                    'The scalloped bezel edge adds an authentic Persian heritage touch.'
                ),
                'stone': ((28, 165, 184), (174, 240, 248)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'فیروزه عجمی صاف نیشابور', 'Gemstone Type', 'Pure Nishapur Ajami turquoise'),
                    ('فرم نگین', 'اشک دامله', 'Stone Shape', 'Teardrop cabochon'),
                    ('وزن تقریبی', '۵٫۲ گرم', 'Approx. Weight', '5.2 g'),
                ],
            },
            {
                'title': 'انگشتر زنانه عقیق شفت‌العبد تراش بیضی',
                'title_en': "Women's Shafa't-al-Abd Agate Ring — Oval Cut",
                'slug': 'انگشتر-زنانه-عقیق-شفت-العبد',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-204',
                'price': 1980000,
                'discount_price': 1690000,
                'stock': 6,
                'is_featured': False,
                'short_description': 'عقیق سرخ تیره شفت‌العبد با تراش ظریف بیضی و رکاب دو بازو.',
                'short_description_en': "Deep-crimson oval Shafa't-al-Abd agate mounted in a sleek split-shank 925 silver band.",
                'full_description': (
                    'انتخابی سبک، خوش‌استایل و پرانرژی برای علاقه‌مندان به سنگ‌های اصیل اسلامی. '
                    'رکاب دو بازوی نقره ۹۲۵ جلوه‌ای مدرن و در عین حال سنتی به این سنگ ارزشمند داده است.'
                ),
                'full_description_en': (
                    'Lightweight, graceful, and uplifting for devotees of classic Islamic gemstones. '
                    'The split-shoulder 925 silver band balances contemporary wearability with timeless tradition.'
                ),
                'stone': ((126, 26, 36), (222, 128, 132)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'عقیق شفت‌العبد طبیعی', 'Gemstone Type', "Natural Shafa't-al-Abd agate"),
                    ('وزن تقریبی', '۴٫۳ گرم', 'Approx. Weight', '4.3 g'),
                ],
            },
            {
                'title': 'انگشتر زنانه آمتیست بنفش رکاب شبکه',
                'title_en': "Women's Royal Purple Amethyst Ring — Lattice Band",
                'slug': 'انگشتر-زنانه-آمتیست-بنفش',
                'category': 'انگشتر-زنانه',
                'product_type': Product.ProductType.RING,
                'sku': 'RNG-205',
                'price': 2350000,
                'discount_price': None,
                'stock': 0,
                'is_featured': False,
                'short_description': 'یاقوت ارغوانی (آمتیست) طبیعی با تراش دامله و رکاب شبکه‌کاری سنتی.',
                'short_description_en': 'Natural royal-purple amethyst cabochon framed in an intricate traditional openwork lattice silver band.',
                'full_description': (
                    'آمتیست طبیعی با طیف بنفش سلطنتی و شفافیت بالا که از دیرباز نماد آرامش ذهن و وقار بوده است.\n\n'
                    'این اثر در حال حاضر به اتمام رسیده و در نوبت تولید کارگاهی قرار دارد.'
                ),
                'full_description_en': (
                    'Translucent royal-purple natural amethyst, historically treasured as an emblem of calm clarity and grace.\n\n'
                    'This edition is currently sold out and scheduled for our next workshop batch.'
                ),
                'stone': ((111, 60, 140), (206, 168, 232)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار شبکه‌کاری', 'Band Material', 'Openwork lattice 925 sterling silver'),
                    ('نوع سنگ', 'آمتیست طبیعی (کوارتز بنفش)', 'Gemstone Type', 'Natural amethyst (violet quartz)'),
                    ('وزن تقریبی', '۶٫۱ گرم', 'Approx. Weight', '6.1 g'),
                ],
            },
            # --- Category 3: حرز و بازوبند ---
            {
                'title': 'حرز امام جواد (ع) دست‌نویس روی پوست آهو با بازوبند چرمی',
                'title_en': 'Imam Jawad (AS) Hand-Written Deerskin Hirz with Leather Armlet',
                'slug': 'حرز-امام-جواد-دست-نویس-پوست-آهو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-301',
                'price': 1850000,
                'discount_price': 1590000,
                'stock': 12,
                'is_featured': True,
                'short_description': 'کتابت دقیق حرز کبیر و صغیر امام جواد (ع) با قلم و جوهر زعفران روی پوست آهو همراه با بازوبند چرم گاوی دست‌دوز.',
                'short_description_en': 'Authentic calligraphy of the Grand & Minor Hirz of Imam Jawad (AS) in saffron ink on tanned deerskin with a hand-stitched cowhide armlet.',
                'full_description': (
                    'این حرز مبارک مطابق نسخه معتبر کتاب «مهج‌الدعوات» سید بن طاووس، پس از رعایت غسل، طهارت، رو به قبله و در ساعات سعد قمر در عقرب‌نبوده، '
                    'با جوهر زعفران و گلاب روی پوست آهوی دباغی‌شده دست‌نویس شده است.\n\n'
                    'شما می‌توانید محفظه نگهداری را از میان قاب نقره استوانه‌ای عیار ۹۲۵، بازوبند چرمی دست‌دوز یا نسخه لول‌شده انتخاب نمایید. '
                    'آداب بستن و دعای همراه حرز به‌صورت چاپی و تاییدشده در بسته ارسال می‌شود.'
                ),
                'full_description_en': (
                    'Transcribed according to the authoritative Muhaj al-Da‘awat text by Sayyid ibn Tawus under full ritual purity, facing Qiblah, and during auspicious lunar hours using pure saffron and rosewater ink on genuine tanned deerskin.\n\n'
                    'Choose your preferred enclosure: an engraved 925 sterling silver cylinder, a hand-stitched cowhide armlet, or an unframed rolled parchment. '
                    'A printed guide covering the recommended prayer and wearing etiquette is included.'
                ),
                'stone': ((88, 52, 34), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس کامل با قلم نی و جوهر زعفران روی پوست آهو', 'Calligraphy', 'Hand-written with reed pen & saffron ink on deerskin'),
                    ('جنس محفظه', 'قابل انتخاب: نقره ۹۲۵ / چرم طبیعی گاوی / لول‌شده', 'Enclosure Options', 'Selectable: 925 silver / genuine cowhide / rolled scroll'),
                    ('متن حرز', 'حرز کبیر امام جواد (ع) طبق سند مهج‌الدعوات', 'Text Source', 'Grand Hirz of Imam Jawad (AS) per Muhaj al-Da‘awat'),
                    ('آداب شرعی', 'دارای گواهی رعایت طهارت، ساعت سعد و نماز حرز', 'Ritual Compliance', 'Certified purity, auspicious timing & accompanying prayer'),
                    ('اقلام همراه', 'دفترچه راهنمای آداب بستن و نگهداری', 'Included Items', 'Printed booklet for wearing etiquette and care'),
                ],
            },
            {
                'title': 'حرز ابی‌دجانه با قاب نقره استوانه‌ای قلم‌زنی',
                'title_en': 'Hirz Abi Dujana with Hand-Engraved Cylindrical Silver Case',
                'slug': 'حرز-ابی-دجانه-قاب-نقره',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-302',
                'price': 2450000,
                'discount_price': None,
                'stock': 7,
                'is_featured': True,
                'short_description': 'حرز شریف ابی‌دجانه انصاری تحریر‌شده روی پوست آهو در محفظه استوانه‌ای نقره ۹۲۵ ضدآب و قلم‌زنی‌شده.',
                'short_description_en': 'Sacred Hirz of Abi Dujana al-Ansari scribed on deerskin inside a waterproof, hand-engraved 925 sterling silver cylinder.',
                'full_description': (
                    'حرز ابی‌دجانه از ادعیه مأثور و مجرب جهت ایمنی منزل، آرامش خانواده و دفع چشم‌زخم و آفات است.\n\n'
                    'لوله نقره ۹۲۵ با درپوش رزوه‌دار محکم و آب‌بندی کامل طراحی شده تا پوست آهو در طول سالیان متمادی از رطوبت محفوظ بماند.'
                ),
                'full_description_en': (
                    'Hirz Abi Dujana is a renowned traditional supplication cherished for household tranquility, safeguarding family well-being, and warding off harm.\n\n'
                    'The threaded 925 silver tube seals hermetically to protect the delicate deerskin parchment from moisture for decades.'
                ),
                'stone': ((74, 44, 28), (200, 169, 106)),
                'style_idx': 1,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس سنتی روی پوست آهو', 'Calligraphy', 'Traditional hand-written scroll on deerskin'),
                    ('جنس محفظه', 'نقره ۹۲۵ عیار قلم‌زنی‌شده با درپوش رزوه‌ای', 'Enclosure Material', 'Hand-engraved 925 silver with threaded cap'),
                    ('طول محفظه', '۴٫۸ سانتی‌متر استاندارد', 'Capsule Length', '4.8 cm standard'),
                    ('وزن قاب نقره', '۱۱٫۲ گرم', 'Silver Case Weight', '11.2 g'),
                    ('امکان آویز', 'دارای دو حلقه جهت استفاده به عنوان بازوبند یا گردن‌آویز', 'Wear Options', 'Dual loops for armlet strap or pendant chain'),
                ],
            },
            {
                'title': 'حرز کبیر امام جواد (ع) قاب نقره دوقلو و بازوبند گاوی',
                'title_en': 'Grand Hirz Imam Jawad (AS) Dual Silver Case & Cowhide Armlet',
                'slug': 'حرز-کبیر-قاب-نقره-دوقلو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-303',
                'price': 2850000,
                'discount_price': 2480000,
                'stock': 5,
                'is_featured': False,
                'short_description': 'مجموعه کامل حرز کبیر و صغیر درون لوله نقره قلم‌زنی با بازوبند چرم طبیعی دست‌دوز و سگک برنجی.',
                'short_description_en': 'Complete Grand & Minor Hirz set sealed in an engraved silver tube with a hand-stitched vegetable-tanned cowhide armlet.',
                'full_description': (
                    'این مجموعه پکیج کامل برای بستن حرز بر بازوی راست مطابق سفارش علما است. '
                    'بند چرمی از چرم گاوی گیاهی دباغی شده که با پوست بدن کاملاً سازگار بوده و ایجاد حساسیت نمی‌کند.'
                ),
                'full_description_en': (
                    'A complete ready-to-wear ensemble designed for wearing on the right upper arm in line with scholarly recommendations. '
                    'Crafted with skin-friendly vegetable-tanned cowhide and a solid brass buckle.'
                ),
                'stone': ((62, 38, 26), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس روی پوست آهو (حرز کبیر + صغیر)', 'Calligraphy', 'Hand-written on deerskin (Grand + Minor Hirz)'),
                    ('جنس محفظه', 'نقره ۹۲۵ عیار و بند چرم طبیعی دست‌دوز', 'Enclosure Material', '925 sterling silver & hand-stitched leather strap'),
                    ('قابلیت تنظیم', 'بند چرمی قابل تنظیم برای تمام سایزهای بازو', 'Adjustability', 'Adjustable leather strap for all arm sizes'),
                    ('گواهی اصالت', 'ممهور به مهر کاتب و گواهی نگارش', 'Certification', 'Stamped with scribe seal and authenticity certificate'),
                ],
            },
            {
                'title': 'حرز شرف‌الشمس اصیل نوزدهم فروردین با محفظه نقره',
                'title_en': 'Authentic 19th Farvardin Sharaf-ol-Shams Hirz with Silver Case',
                'slug': 'حرز-شرف-الشمس-پوست-آهو',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-304',
                'price': 1920000,
                'discount_price': None,
                'stock': 9,
                'is_featured': False,
                'short_description': 'لوح کامل شرف‌الشمس و اسماء حسنی تحریرشده در روز ۱۹ فروردین روی پوست آهو با محفظه نقره.',
                'short_description_en': 'Complete Sharaf-ol-Shams seal and Divine Names inscribed specifically on the 19th of Farvardin on deerskin with silver capsule.',
                'full_description': (
                    'تألیف شرف‌الشمس شامل نقش خاتم نبوت، حروف مقطعه و ادعیه مأثوره که در ساعت شرف خورشید نوزدهم فروردین با مرکب زعفران بر پوست آهو نگاشته شده است.'
                ),
                'full_description_en': (
                    'Includes the traditional Seal of Prophethood geometry and sacred invocations inscribed in saffron ink during the solar exaltation window of 19th Farvardin on genuine deerskin.'
                ),
                'stone': ((98, 62, 34), (168, 126, 48)),
                'style_idx': 1,
                'specs': [
                    ('نوع نگارش', 'تحریر در ساعت شرف نوزدهم فروردین روی پوست آهو', 'Calligraphy', 'Inscribed on 19th Farvardin solar hour on deerskin'),
                    ('جنس محفظه', 'نقره ۹۲۵ / بند چرمی دست‌دوز', 'Enclosure Material', '925 silver / hand-stitched leather strap'),
                    ('ابعاد رول', 'بسته استوانه‌ای جمع‌وجور ۴ سانتی‌متری', 'Dimensions', 'Compact 4 cm cylindrical capsule'),
                ],
            },
            {
                'title': 'بازوبند حرز صغیر و دعای عهد دست‌نویس با جلد چرمی',
                'title_en': 'Minor Hirz & Dua Ahd Hand-Written Scroll with Leather Pouch',
                'slug': 'بازوبند-حرز-صغیر-جلد-چرمی',
                'category': 'حرز-و-بازوبند',
                'product_type': Product.ProductType.HIRZ,
                'sku': 'HRZ-305',
                'price': 1180000,
                'discount_price': None,
                'stock': 10,
                'is_featured': False,
                'short_description': 'نسخه سبک و روزمره حرز صغیر امام جواد (ع) در غلاف چرمی دست‌دوز قابل بستن روی بازو یا قرارگیری در کیف.',
                'short_description_en': 'Featherlight everyday edition of the Minor Hirz in a hand-sewn leather sleeve suitable for arm wear or pocket carry.',
                'full_description': (
                    'طراحی‌شده برای افرادی که به دنبال حرز سبک و راحت برای استفاده مداوم هستند. '
                    'پوست آهو پس از نگارش در لایه محافظ قرار گرفته و داخل بازوبند چرمی دوخته شده است.'
                ),
                'full_description_en': (
                    'Tailored for daily comfort and effortless portability. After transcription, the deerskin scroll is sealed in a protective sleeve inside hand-stitched cowhide.'
                ),
                'stone': ((104, 68, 44), (15, 61, 62)),
                'style_idx': 0,
                'specs': [
                    ('نوع نگارش', 'دست‌نویس حرز صغیر روی پوست آهو', 'Calligraphy', 'Hand-written Minor Hirz on deerskin'),
                    ('جنس محفظه', 'چرم طبیعی گاوی دست‌دوز / قاب نقره انتخابی', 'Enclosure Material', 'Hand-stitched cowhide / optional silver tube'),
                    ('وزن کل', '۱۸ گرم بسیار سبک', 'Total Weight', '18 g ultra-lightweight'),
                ],
            },
            # --- Category 4: سنگ‌های معدنی اصیل ---
            {
                'title': 'انگشتر شجر پاییزی قائنات کلکسیونی رکاب دست‌ساز',
                'title_en': "Collector's Qaenat Autumn Scenic Agate Ring — Handcrafted Band",
                'slug': 'انگشتر-شجر-پاییزی-قائنات',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-401',
                'price': 3750000,
                'discount_price': 3290000,
                'stock': 3,
                'is_featured': True,
                'short_description': 'عقیق شجر طبیعی قائنات با نقش درختان پاییزی واضح و تکرارناپذیر در رکاب نقره ۹۲۵.',
                'short_description_en': 'One-of-a-kind natural Qaenat dendritic agate displaying vivid autumn tree formations in a handcrafted 925 silver ring.',
                'full_description': (
                    'در دل این سنگ معدنی اصیل از منطقه قائنات خراسان، رسوبات منگنز و آهن طی میلیون‌ها سال منظره طبیعی درختان پاییزی را نقش بسته‌اند.\n\n'
                    'هر سنگ شجر در دنیا کاملاً منحصربه‌فرد است و هیچ نسخه مشابهی از آن وجود ندارد.'
                ),
                'full_description_en': (
                    'Formed over millennia by natural manganese and iron mineral inclusions inside translucent chalcedony from Qaenat in Khorasan, this stone captures an unmistakable autumn forest silhouette.\n\n'
                    'Every scenic dendritic agate is completely one-of-a-kind.'
                ),
                'stone': ((158, 108, 62), (234, 198, 152)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار دست‌ساز', 'Band Material', 'Handcrafted 925 sterling silver'),
                    ('نوع سنگ', 'عقیق شجر پاییزی طبیعی قائنات', 'Gemstone Type', 'Natural Qaenat autumn scenic agate'),
                    ('ویژگی شاخص', 'منظره طبیعی تک‌نسخه بدون هیچ بهسازی', 'Highlight', 'One-of-a-kind natural landscape, unenhanced'),
                    ('وزن تقریبی', '۱۵٫۹ گرم', 'Approx. Weight', '15.9 g'),
                ],
            },
            {
                'title': 'انگشتر زبرجد سبز معدنی تراش فست رکاب ناودانی',
                'title_en': 'Natural Green Peridot Ring — Faceted Cut Channel Band',
                'slug': 'انگشتر-زبرجد-سبز-معدنی',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-402',
                'price': 3900000,
                'discount_price': None,
                'stock': 4,
                'is_featured': False,
                'short_description': 'سنگ زبرجد طبیعی (پریدوت) با شفافیت کریستالی سبز زیتونی در رکاب نقره ۹۲۵.',
                'short_description_en': 'Lively olive-green natural faceted peridot set into a clean 925 sterling silver channel band.',
                'full_description': (
                    'زبرجد سبز معدنی از سنگ‌های قیمتی با طیف سبز طلایی زنده است که زیر نور روز درخشش استثنایی دارد.\n\n'
                    'در کتب جواهرشناسی قدیم، زبرجد به‌عنوان سنگ گشایش روزی و رفع اندوه معرفی شده است.'
                ),
                'full_description_en': (
                    'Natural mineral peridot radiates a distinctive golden-olive green glow that sparkles brilliantly in natural daylight.\n\n'
                    'In classical gemological lore, peridot is associated with vitality, abundance, and uplifting spirit.'
                ),
                'stone': ((107, 158, 56), (194, 232, 134)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'زبرجد معدنی طبیعی (Peridot)', 'Gemstone Type', 'Natural mineral peridot'),
                    ('نوع تراش', 'فست مستطیلی درخشان', 'Cut', 'Radiant rectangular faceted cut'),
                    ('وزن تقریبی', '۱۳٫۲ گرم', 'Approx. Weight', '13.2 g'),
                ],
            },
            {
                'title': 'انگشتر عقیق سلیمانی چشم‌دار طبیعی',
                'title_en': 'Natural Eye Suleimani Agate Ring',
                'slug': 'انگشتر-عقیق-سلیمانی-چشم-دار',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-403',
                'price': 2750000,
                'discount_price': None,
                'stock': 6,
                'is_featured': False,
                'short_description': 'عقیق سلیمانی با دایره‌های متحدالمرکز طبیعی (چشم سلیمانی) و رکاب نقره دست‌ساز.',
                'short_description_en': 'Natural banded Suleimani eye agate displaying concentric rings in a handcrafted 925 silver bezel.',
                'full_description': (
                    'عقیق سلیمانی با خطوط طبیعی لایه‌لایه و مرکز متقارن، از سنگ‌های کلکسیونی مورد توجه علاقه‌مندان به احجار کریمه است.\n\n'
                    'رکاب نقره با لبه‌های چنگ‌دار محکم، محافظت کامل از حاشیه سنگ را تضمین می‌کند.'
                ),
                'full_description_en': (
                    'Adorned with naturally formed concentric bands resembling a watchful eye, Suleimani agate is a beloved collector gemstone.\n\n'
                    'The sturdy pronged 925 silver rim firmly shields the stone perimeter.'
                ),
                'stone': ((86, 68, 62), (198, 174, 162)),
                'style_idx': 2,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'عقیق سلیمانی معدنی طبیعی', 'Gemstone Type', 'Natural Suleimani eye agate'),
                    ('وزن تقریبی', '۱۴٫۵ گرم', 'Approx. Weight', '14.5 g'),
                ],
            },
            {
                'title': 'انگشتر باباقوری سه‌پوست یمنی اصیل',
                'title_en': 'Authentic Yemeni Three-Layer Babaghori Onyx Ring',
                'slug': 'انگشتر-باباقوری-سه-پوست-یمنی',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-404',
                'price': 3150000,
                'discount_price': 2690000,
                'stock': 2,
                'is_featured': False,
                'short_description': 'سنگ باباقوری سه‌پوست طبیعی با تضاد رنگی چشم‌نواز مشکی و سفید و رکاب شیرازی.',
                'short_description_en': 'Natural three-layer black-and-white Yemeni Babaghori onyx cabochon in a classic Shirazi 925 silver setting.',
                'full_description': (
                    'باباقوری سه‌پوست اصیل از خانواده جزع یمانی است که لایه‌های سفید و سیاه آن با برش دامله به‌صورت کامل تفکیک شده‌اند.\n\n'
                    'این سنگ در فرهنگ ایرانی و عربی به دفع نظر بد شهرت دارد.'
                ),
                'full_description_en': (
                    'From the classical Yemeni onyx family, this three-layer Babaghori stone exhibits crisp monochrome bands sculpted by cabochon dome cutting.\n\n'
                    'Long revered in Persian and Middle Eastern traditions as a protective talismanic stone.'
                ),
                'stone': ((42, 42, 46), (225, 225, 230)),
                'style_idx': 0,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ طرح شیرازی', 'Band Material', 'Shirazi-style 925 sterling silver'),
                    ('نوع سنگ', 'جزع سه‌پوست طبیعی (باباقوری)', 'Gemstone Type', 'Natural three-layer Babaghori onyx'),
                    ('وزن تقریبی', '۱۵٫۱ گرم', 'Approx. Weight', '15.1 g'),
                ],
            },
            {
                'title': 'انگشتر توپاز آبی لندن با رکاب نقره ۹۲۵',
                'title_en': 'London Blue Topaz 925 Sterling Silver Ring',
                'slug': 'انگشتر-توپاز-آبی-لندن',
                'category': 'سنگ-های-معدنی-اصیل',
                'product_type': Product.ProductType.RING,
                'sku': 'GEM-405',
                'price': 3400000,
                'discount_price': None,
                'stock': 5,
                'is_featured': False,
                'short_description': 'نگین توپاز آبی عمیق (London Blue) با تلألو خیره‌کننده روی رکاب خوش‌تراش نقره.',
                'short_description_en': 'Deep ocean-hued London Blue topaz with radiant brilliance mounted in a tailored 925 sterling silver ring.',
                'full_description': (
                    'توپاز آبی با شفافیت بسیار بالا و سختی ۸ موس، انتخابی ماندگار و مقاوم برای استفاده همیشگی در کنار استایل‌های کلاسیک و رسمی است.'
                ),
                'full_description_en': (
                    'Boasting high optical clarity and a Mohs hardness of 8, London Blue topaz offers durable brilliance suited for both classic and formal attire.'
                ),
                'stone': ((22, 92, 134), (144, 212, 245)),
                'style_idx': 1,
                'specs': [
                    ('جنس رکاب', 'نقره ۹۲۵ عیار', 'Band Material', '925 sterling silver'),
                    ('نوع سنگ', 'توپاز آبی لندن طبیعی', 'Gemstone Type', 'Natural London Blue topaz'),
                    ('سختی سنگ', '۸ در مقیاس موس', 'Mohs Hardness', '8 on Mohs scale'),
                    ('وزن تقریبی', '۱۳٫۹ گرم', 'Approx. Weight', '13.9 g'),
                ],
            },
        ]

        gallery_themes = [
            ('نمایه استودیویی روی مخمل زمردی', 'Studio view on emerald velvet', (15, 61, 62), (9, 36, 37)),
            ('نمایه کارگاهی با گواهی اصالت', 'Workshop view with authenticity seal', (243, 238, 228), (224, 214, 194)),
        ]

        for idx, pdata in enumerate(products_data, start=1):
            category = categories_by_slug[pdata['category']]
            product, _ = Product.objects.update_or_create(
                sku=pdata['sku'],
                defaults={
                    'title': pdata['title'],
                    'title_en': pdata['title_en'],
                    'slug': pdata['slug'],
                    'category': category,
                    'product_type': pdata['product_type'],
                    'price': pdata['price'],
                    'discount_price': pdata['discount_price'],
                    'stock': pdata['stock'],
                    'short_description': pdata['short_description'],
                    'short_description_en': pdata['short_description_en'],
                    'full_description': pdata['full_description'],
                    'full_description_en': pdata['full_description_en'],
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
            for g_idx, (alt_label, alt_label_en, g_top, g_bot) in enumerate(gallery_themes, start=1):
                g_img = ProductImage(
                    product=product,
                    alt_text=f'{product.title} — {alt_label}',
                    alt_text_en=f'{product.title_en} — {alt_label_en}',
                )
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
                    ProductSpecification(
                        product=product,
                        key=k_fa,
                        key_en=k_en,
                        value=v_fa,
                        value_en=v_en,
                    )
                    for k_fa, v_fa, k_en, v_en in pdata['specs']
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'عملیات با موفقیت انجام شد: {len(categories_data)} دسته‌بندی و {len(products_data)} محصول همراه با تصاویر و مشخصات فنی ذخیره شدند.'
            )
        )
