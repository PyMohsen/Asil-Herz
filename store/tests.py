from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product
from .templatetags.store_filters import comma_fa, fa_digits, toman


class TemplateFiltersTests(TestCase):
    def test_persian_price_and_digit_filters(self):
        self.assertEqual(toman(2450000), '۲,۴۵۰,۰۰۰ تومان')
        self.assertEqual(comma_fa(1850000), '۱,۸۵۰,۰۰۰')
        self.assertEqual(fa_digits('56-66'), '۵۶-۶۶')
        self.assertEqual(toman(None), '')


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='انگشتر آزمایشی')
        self.dummy_image = SimpleUploadedFile('test.jpg', b'JPEGDATA', content_type='image/jpeg')

    def test_discount_properties_and_unicode_slug(self):
        product = Product.objects.create(
            title='انگشتر عقیق آزمایشی',
            category=self.category,
            product_type=Product.ProductType.RING,
            sku='TST-001',
            price=2000000,
            discount_price=1500000,
            stock=3,
            short_description='توضیح کوتاه',
            full_description='توضیح کامل',
            main_image=self.dummy_image,
        )
        self.assertEqual(product.slug, 'انگشتر-عقیق-آزمایشی')
        self.assertTrue(product.has_discount)
        self.assertEqual(product.get_final_price, 1500000)
        self.assertEqual(product.discount_percentage, 25)

    def test_invalid_discount_price_raises_validation_error(self):
        product = Product(
            title='محصول نامعتبر',
            category=self.category,
            product_type=Product.ProductType.RING,
            sku='TST-002',
            price=1000000,
            discount_price=1200000,
            stock=1,
            short_description='کوتاه',
            full_description='کامل',
            main_image=self.dummy_image,
        )
        with self.assertRaises(ValidationError):
            product.clean()


class StorefrontIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo')

    def test_home_page_renders_persian_rtl_and_featured_content(self):
        resp = self.client.get(reverse('store:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'lang="fa" dir="rtl"')
        self.assertContains(resp, 'گالری جواهرات و حرز اصیل')
        self.assertContains(resp, 'ضمانت اصالت سنگ و نقره')
        self.assertContains(resp, 'گواهی اصالت نگارش و آداب حرز')
        self.assertContains(resp, 'Vazirmatn')

    def test_catalog_filters_sorting_and_pagination(self):
        base_url = reverse('store:product_list')

        resp = self.client.get(base_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_count'], 20)
        self.assertTrue(resp.context['page_obj'].has_next())

        # Filter by type=hirz and preserve on pagination/sort
        hirz_resp = self.client.get(base_url, {'type': 'hirz', 'sort': 'cheapest'})
        self.assertEqual(hirz_resp.status_code, 200)
        self.assertEqual(hirz_resp.context['total_count'], 5)
        prices = [p.get_final_price for p in hirz_resp.context['products']]
        self.assertEqual(prices, sorted(prices))

        # In-stock filter excludes RNG-205 (stock=0)
        in_stock_resp = self.client.get(base_url, {'in_stock': '1'})
        self.assertEqual(in_stock_resp.context['total_count'], 19)

        # Price range + keyword search
        search_resp = self.client.get(base_url, {'q': 'در نجف', 'min_price': '2000000'})
        self.assertEqual(search_resp.status_code, 200)
        self.assertGreaterEqual(search_resp.context['total_count'], 1)

    def test_product_detail_conditional_selectors_for_ring_and_hirz(self):
        ring = Product.objects.filter(product_type=Product.ProductType.RING).first()
        ring_resp = self.client.get(ring.get_absolute_url())
        self.assertEqual(ring_resp.status_code, 200)
        self.assertContains(ring_resp, 'راهنمای تعیین سایز انگشتر')
        self.assertContains(ring_resp, '۵۶')
        self.assertContains(ring_resp, '۶۶')
        self.assertEqual(len(ring_resp.context['related_products']), 4)

        hirz = Product.objects.filter(product_type=Product.ProductType.HIRZ).first()
        hirz_resp = self.client.get(hirz.get_absolute_url())
        self.assertEqual(hirz_resp.status_code, 200)
        self.assertContains(hirz_resp, 'قاب نقره استوانه‌ای')
        self.assertContains(hirz_resp, 'بازوبند چرمی دست‌دوز')
        self.assertContains(hirz_resp, 'بدون قاب / لول‌شده')
        self.assertNotContains(hirz_resp, 'id="size-guide-title"')
        self.assertEqual(len(hirz_resp.context['related_products']), 4)

    def test_session_cart_add_and_remove_workflow(self):
        ring = Product.objects.filter(product_type=Product.ProductType.RING, stock__gt=0).first()
        add_url = reverse('store:add_to_cart')
        resp = self.client.post(
            add_url,
            data={'product_id': ring.id, 'quantity': 2, 'variant': 'سایز ۶۰'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['cart_count'], 2)

        # Verify session persists on subsequent page request
        home_resp = self.client.get(reverse('store:home'))
        self.assertEqual(home_resp.context['cart_count'], 2)

        # Remove item
        remove_url = reverse('store:remove_from_cart')
        item_key = f'{ring.id}:سایز ۶۰'
        rem_resp = self.client.post(
            remove_url,
            data={'item_key': item_key},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(rem_resp.status_code, 200)
        self.assertEqual(rem_resp.json()['cart_count'], 0)

    def test_out_of_stock_product_cannot_be_added_to_cart(self):
        oos = Product.objects.get(sku='RNG-205')
        resp = self.client.post(
            reverse('store:add_to_cart'),
            data={'product_id': oos.id, 'quantity': 1, 'variant': 'سایز ۵۸'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])
