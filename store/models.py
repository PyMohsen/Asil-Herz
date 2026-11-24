from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def _build_unique_slug(instance, source_text: str, field_name: str = 'slug') -> str:
    """Generate a unique Unicode-friendly slug preserving Persian characters."""
    normalized = (source_text or '').replace('\u200c', '-').strip()
    base_slug = slugify(normalized, allow_unicode=True) or 'item'
    candidate = base_slug
    counter = 2
    model_cls = instance.__class__
    while model_cls.objects.filter(**{field_name: candidate}).exclude(pk=instance.pk).exists():
        candidate = f'{base_slug}-{counter}'
        counter += 1
    return candidate


class Category(models.Model):
    """Product category for rings, gemstones, and traditional Hirz artifacts."""

    title = models.CharField(max_length=150, verbose_name='عنوان دسته‌بندی')
    slug = models.SlugField(
        max_length=180,
        unique=True,
        allow_unicode=True,
        blank=True,
        verbose_name='نامک (URL)',
        help_text='در صورت خالی بودن، به‌صورت خودکار از عنوان ساخته می‌شود.',
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        verbose_name='تصویر دسته‌بندی',
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['id']

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(self, self.title)
        super().save(*args, **kwargs)


class Product(models.Model):
    """Silver rings, natural gemstones, and traditional scribal Hirz products."""

    class ProductType(models.TextChoices):
        RING = 'ring', 'انگشتر نقره و سنگ قیمتی'
        HIRZ = 'hirz', 'حرز و بازوبند سنتی'

    title = models.CharField(max_length=220, verbose_name='عنوان محصول')
    slug = models.SlugField(
        max_length=240,
        unique=True,
        allow_unicode=True,
        blank=True,
        verbose_name='نامک (URL)',
        help_text='در صورت خالی بودن، به‌صورت خودکار از عنوان ساخته می‌شود.',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='دسته‌بندی',
    )
    product_type = models.CharField(
        max_length=16,
        choices=ProductType.choices,
        default=ProductType.RING,
        verbose_name='نوع محصول',
    )
    sku = models.CharField(max_length=50, unique=True, verbose_name='شناسه کالا (SKU)')
    price = models.PositiveIntegerField(verbose_name='قیمت اصلی (تومان)')
    discount_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='قیمت با تخفیف (تومان)',
    )
    stock = models.PositiveIntegerField(default=0, verbose_name='موجودی انبار')
    short_description = models.TextField(verbose_name='معرفی کوتاه')
    full_description = models.TextField(verbose_name='توضیحات کامل و خواص')
    main_image = models.ImageField(upload_to='products/main/', verbose_name='تصویر اصلی')
    is_featured = models.BooleanField(default=False, verbose_name='محصول ویژه')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_type', 'is_featured']),
            models.Index(fields=['category', 'created_at']),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        if self.discount_price is not None:
            if self.discount_price == 0:
                raise ValidationError({'discount_price': 'قیمت با تخفیف باید بیشتر از صفر باشد.'})
            if self.price and self.discount_price >= self.price:
                raise ValidationError(
                    {'discount_price': 'قیمت با تخفیف باید کمتر از قیمت اصلی محصول باشد.'}
                )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(self, self.title)
        super().save(*args, **kwargs)

    @property
    def has_discount(self) -> bool:
        return (
            self.discount_price is not None
            and 0 < self.discount_price < self.price
        )

    @property
    def get_final_price(self) -> int:
        if self.has_discount:
            return self.discount_price
        return self.price

    @property
    def discount_percentage(self) -> int:
        if not self.has_discount or self.price <= 0:
            return 0
        return round(((self.price - self.discount_price) / self.price) * 100)

    @property
    def is_in_stock(self) -> bool:
        return self.stock > 0

    def get_absolute_url(self) -> str:
        return reverse('store:product_detail', kwargs={'slug': self.slug})


class ProductImage(models.Model):
    """Additional gallery images for a product."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='محصول',
    )
    image = models.ImageField(upload_to='products/gallery/', verbose_name='تصویر گالری')
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='متن جایگزین')

    class Meta:
        verbose_name = 'تصویر گالری محصول'
        verbose_name_plural = 'تصاویر گالری محصول'
        ordering = ['id']

    def __str__(self) -> str:
        return self.alt_text or f'تصویر {self.product.title}'


class ProductSpecification(models.Model):
    """Dynamic technical specification key-value rows for rings and Hirz artifacts."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name='محصول',
    )
    key = models.CharField(max_length=120, verbose_name='عنوان مشخصه')
    value = models.CharField(max_length=255, verbose_name='مقدار مشخصه')

    class Meta:
        verbose_name = 'مشخصه فنی'
        verbose_name_plural = 'مشخصات فنی'
        ordering = ['id']

    def __str__(self) -> str:
        return f'{self.key}: {self.value}'
