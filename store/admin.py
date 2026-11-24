from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductImage, ProductSpecification
from .templatetags.store_filters import fa_digits, toman

admin.site.site_header = 'پنل مدیریت گالری جواهرات و حرز اصیل'
admin.site.site_title = 'مدیریت فروشگاه'
admin.site.index_title = 'داشبورد مدیریت محصولات و دسته‌بندی‌ها'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 2
    fields = ('image', 'preview', 'alt_text')
    readonly_fields = ('preview',)

    @admin.display(description='پیش‌نمایش')
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
    fields = ('key', 'value')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'title', 'slug', 'product_count')
    search_fields = ('title', 'description')
    readonly_fields = ('thumbnail',)

    @admin.display(description='تصویر')
    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:8px;border:1px solid #d6cec0;" />',
                obj.image.url,
            )
        return '—'

    @admin.display(description='تعداد محصولات')
    def product_count(self, obj):
        return fa_digits(obj.products.count())


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline, ProductSpecificationInline]
    list_display = (
        'thumbnail',
        'title',
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
    search_fields = ('title', 'sku', 'short_description')
    list_editable = ('stock', 'is_featured')
    readonly_fields = ('created_at', 'thumbnail')
    fieldsets = (
        (
            'اطلاعات اصلی اثر',
            {
                'fields': (
                    'title',
                    'slug',
                    'category',
                    'product_type',
                    'sku',
                    'is_featured',
                )
            },
        ),
        (
            'قیمت‌گذاری و موجودی',
            {
                'fields': (
                    'price',
                    'discount_price',
                    'stock',
                )
            },
        ),
        (
            'توضیحات و تصویر اصلی',
            {
                'fields': (
                    'short_description',
                    'full_description',
                    'main_image',
                    'thumbnail',
                    'created_at',
                )
            },
        ),
    )

    @admin.display(description='تصویر')
    def thumbnail(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:cover;border-radius:8px;border:1px solid #d6cec0;" />',
                obj.main_image.url,
            )
        return '—'

    @admin.display(description='قیمت اصلی', ordering='price')
    def formatted_price(self, obj):
        return toman(obj.price)

    @admin.display(description='قیمت نهایی')
    def formatted_final_price(self, obj):
        if obj.has_discount:
            return format_html(
                '<strong style="color:#0F3D3E;">{}</strong> <span style="color:#991b1b;font-size:11px;">({}٪ تخفیف)</span>',
                toman(obj.get_final_price),
                fa_digits(obj.discount_percentage),
            )
        return toman(obj.get_final_price)
