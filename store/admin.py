from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, Product, ProductImage, ProductSpecification
from .templatetags.store_filters import fa_digits, is_persian_locale, toman

admin.site.site_header = _('Asil Jewelry & Hirz Gallery Admin')
admin.site.site_title = _('Store Administration')
admin.site.index_title = _('Products & Categories Management Dashboard')


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 2
    fields = ('image', 'preview', 'alt_text', 'alt_text_en')
    readonly_fields = ('preview',)

    @admin.display(description=_('Preview'))
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:48px;width:48px;object-fit:cover;border-radius:8px;border:1px solid #d6cec0;" />',
                obj.image.url,
            )
        return '—'


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 3
    fields = ('key', 'key_en', 'value', 'value_en')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'title', 'title_en', 'slug', 'product_count')
    search_fields = ('title', 'title_en', 'description', 'description_en')
    readonly_fields = ('thumbnail',)
    fieldsets = (
        (
            _('Persian Content'),
            {
                'fields': ('title', 'slug', 'description', 'image', 'thumbnail'),
            },
        ),
        (
            _('English Content'),
            {
                'fields': ('title_en', 'description_en'),
            },
        ),
    )

    @admin.display(description=_('Image'))
    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:8px;border:1px solid #d6cec0;" />',
                obj.image.url,
            )
        return '—'

    @admin.display(description=_('Product count'))
    def product_count(self, obj):
        return fa_digits(obj.products.count())


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline, ProductSpecificationInline]
    list_display = (
        'thumbnail',
        'title',
        'title_en',
        'sku',
        'category',
        'product_type',
        'formatted_price',
        'formatted_final_price',
        'stock',
        'is_featured',
        'created_at',
    )
    list_display_links = ('thumbnail', 'title')
    list_filter = ('category', 'product_type', 'is_featured', 'created_at')
    search_fields = ('title', 'title_en', 'sku', 'short_description', 'short_description_en')
    list_editable = ('stock', 'is_featured')
    readonly_fields = ('created_at', 'thumbnail')
    fieldsets = (
        (
            _('Core Product Info'),
            {
                'fields': (
                    'title',
                    'title_en',
                    'slug',
                    'category',
                    'product_type',
                    'sku',
                    'is_featured',
                )
            },
        ),
        (
            _('Pricing & Inventory'),
            {
                'fields': (
                    'price',
                    'discount_price',
                    'stock',
                )
            },
        ),
        (
            _('Descriptions & Main Image'),
            {
                'fields': (
                    'short_description',
                    'short_description_en',
                    'full_description',
                    'full_description_en',
                    'main_image',
                    'thumbnail',
                    'created_at',
                )
            },
        ),
    )

    @admin.display(description=_('Image'))
    def thumbnail(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:cover;border-radius:8px;border:1px solid #d6cec0;" />',
                obj.main_image.url,
            )
        return '—'

    @admin.display(description=_('Original price'), ordering='price')
    def formatted_price(self, obj):
        return toman(obj.price)

    @admin.display(description=_('Final price'))
    def formatted_final_price(self, obj):
        if obj.has_discount:
            pct = fa_digits(obj.discount_percentage)
            badge = f'({pct}٪ {_("off")})' if is_persian_locale() else f'({pct}% {_("off")})'
            return format_html(
                '<strong style="color:#0F3D3E;">{}</strong> <span style="color:#991b1b;font-size:11px;">{}</span>',
                toman(obj.get_final_price),
                badge,
            )
        return toman(obj.get_final_price)
