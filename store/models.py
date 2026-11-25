from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import get_language, gettext_lazy as _


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


def _localized_attr(obj, field_name: str) -> str:
    """Return English field value when English is active, falling back to primary field."""
    lang = (get_language() or 'fa').split('-')[0]
    if lang == 'en':
        en_value = getattr(obj, f'{field_name}_en', '')
        if en_value:
            return en_value
    return getattr(obj, field_name, '')


class Category(models.Model):
    """Product category for rings, gemstones, and traditional Hirz artifacts."""

    title = models.CharField(max_length=150, verbose_name=_('Category title'))
    title_en = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name=_('Category title (English)'),
    )
    slug = models.SlugField(
        max_length=180,
        unique=True,
        allow_unicode=True,
        blank=True,
        verbose_name=_('Slug (URL)'),
        help_text=_('If left blank, automatically generated from the title.'),
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        verbose_name=_('Category image'),
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))
    description_en = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Description (English)'),
    )

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['id']

    @property
    def localized_title(self) -> str:
        return _localized_attr(self, 'title')

    @property
    def localized_description(self) -> str:
        return _localized_attr(self, 'description')

    def __str__(self) -> str:
        return self.localized_title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(self, self.title)
        super().save(*args, **kwargs)


class Product(models.Model):
    """Silver rings, natural gemstones, and traditional scribal Hirz products."""

    class ProductType(models.TextChoices):
        RING = 'ring', _('Silver ring & gemstone')
        HIRZ = 'hirz', _('Traditional Hirz & armlet')

    title = models.CharField(max_length=220, verbose_name=_('Product title'))
    title_en = models.CharField(
        max_length=220,
        blank=True,
        default='',
        verbose_name=_('Product title (English)'),
    )
    slug = models.SlugField(
        max_length=240,
        unique=True,
        allow_unicode=True,
        blank=True,
        verbose_name=_('Slug (URL)'),
        help_text=_('If left blank, automatically generated from the title.'),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name=_('Category'),
    )
    product_type = models.CharField(
        max_length=16,
        choices=ProductType.choices,
        default=ProductType.RING,
        verbose_name=_('Product type'),
    )
    sku = models.CharField(max_length=50, unique=True, verbose_name=_('Product SKU'))
    price = models.PositiveIntegerField(verbose_name=_('Original price (Toman)'))
    discount_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Discounted price (Toman)'),
    )
    stock = models.PositiveIntegerField(default=0, verbose_name=_('Stock quantity'))
    short_description = models.TextField(verbose_name=_('Short description'))
    short_description_en = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Short description (English)'),
    )
    full_description = models.TextField(verbose_name=_('Full description & properties'))
    full_description_en = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Full description & properties (English)'),
    )
    main_image = models.ImageField(upload_to='products/main/', verbose_name=_('Main image'))
    is_featured = models.BooleanField(default=False, verbose_name=_('Featured product'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_type', 'is_featured']),
            models.Index(fields=['category', 'created_at']),
        ]

    @property
    def localized_title(self) -> str:
        return _localized_attr(self, 'title')

    @property
    def localized_short_description(self) -> str:
        return _localized_attr(self, 'short_description')

    @property
    def localized_full_description(self) -> str:
        return _localized_attr(self, 'full_description')

    def __str__(self) -> str:
        return self.localized_title

    def clean(self):
        super().clean()
        if self.discount_price is not None:
            if self.discount_price == 0:
                raise ValidationError({'discount_price': _('Discounted price must be greater than zero.')})
            if self.price and self.discount_price >= self.price:
                raise ValidationError(
                    {'discount_price': _('Discounted price must be less than the original price.')}
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
        verbose_name=_('Product'),
    )
    image = models.ImageField(upload_to='products/gallery/', verbose_name=_('Gallery image'))
    alt_text = models.CharField(max_length=200, blank=True, verbose_name=_('Alt text'))
    alt_text_en = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('Alt text (English)'),
    )

    class Meta:
        verbose_name = _('Product gallery image')
        verbose_name_plural = _('Product gallery images')
        ordering = ['id']

    @property
    def localized_alt_text(self) -> str:
        lang = (get_language() or 'fa').split('-')[0]
        if lang == 'en':
            return self.alt_text_en or self.product.localized_title
        return self.alt_text or self.product.localized_title

    def __str__(self) -> str:
        return self.localized_alt_text or _('Image of %(title)s') % {'title': self.product.localized_title}


class ProductSpecification(models.Model):
    """Dynamic technical specification key-value rows for rings and Hirz artifacts."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name=_('Product'),
    )
    key = models.CharField(max_length=120, verbose_name=_('Specification name'))
    key_en = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('Specification name (English)'),
    )
    value = models.CharField(max_length=255, verbose_name=_('Specification value'))
    value_en = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Specification value (English)'),
    )

    class Meta:
        verbose_name = _('Technical specification')
        verbose_name_plural = _('Technical specifications')
        ordering = ['id']

    @property
    def localized_key(self) -> str:
        return _localized_attr(self, 'key')

    @property
    def localized_value(self) -> str:
        return _localized_attr(self, 'value')

    def __str__(self) -> str:
        return f'{self.localized_key}: {self.localized_value}'
