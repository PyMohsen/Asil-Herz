from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from .models import Category, Product
from .templatetags.store_filters import comma_fa, fa_digits, toman


class TemplateFiltersTests(TestCase):
    def test_persian_price_and_digit_filters(self):
        self.assertEqual(toman(2450000), '۲,۴۵۰,۰۰۰ تومان')
        self.assertEqual(comma_fa(1850000), '۱,۸۵۰,۰۰۰')
        self.assertEqual(fa_digits('56-66'), '۵۶-۶۶')
        self.assertEqual(toman(None), '')

    def test_english_price_and_digit_filters(self):
        with translation.override('en'):
            self.assertEqual(toman(2450000), '2,450,000 Toman')
            self.assertEqual(comma_fa(1850000), '1,850,000')
            self.assertEqual(fa_digits('۵۶-۶۶'), '56-66')
            self.assertEqual(toman(None), '')


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='انگشتر آزمایشی', title_en='Test Rings')
        self.dummy_image = SimpleUploadedFile('test.jpg', b'JPEGDATA', content_type='image/jpeg')

    def test_discount_properties_and_unicode_slug(self):
        product = Product.objects.create(
            title='انگشتر عقیق آزمایشی',
            title_en='Test Agate Ring',
            category=self.category,
            product_type=Product.ProductType.RING,
            sku='TST-001',
            price=2000000,
            discount_price=1500000,
            stock=3,
            short_description='توضیح کوتاه',
            short_description_en='Short summary',
            full_description='توضیح کامل',
            main_image=self.dummy_image,
        )
        self.assertEqual(product.slug, 'انگشتر-عقیق-آزمایشی')
        self.assertTrue(product.has_discount)
        self.assertEqual(product.get_final_price, 1500000)
        self.assertEqual(product.discount_percentage, 25)

        with translation.override('en'):
            self.assertEqual(product.localized_title, 'Test Agate Ring')
            self.assertEqual(product.localized_short_description, 'Short summary')
            # Falls back cleanly when full_description_en is empty
            self.assertEqual(product.localized_full_description, 'توضیح کامل')

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
        self.assertContains(resp, 'id="language-switcher-btn"')
        self.assertContains(resp, 'value="en"')

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


class BilingualStorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo')

    def setUp(self):
        super().setUp()
        translation.activate(settings.LANGUAGE_CODE)

    def tearDown(self):
        translation.activate(settings.LANGUAGE_CODE)
        super().tearDown()

    def test_english_home_page_renders_ltr_and_translated_content(self):
        with translation.override('en'):
            en_home_url = reverse('store:home')
        self.assertEqual(en_home_url, '/en/')

        resp = self.client.get(en_home_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'lang="en" dir="ltr"')
        self.assertContains(resp, 'Asil Jewelry & Hirz Gallery')
        self.assertContains(resp, 'Gemstone & Silver Authenticity')
        self.assertContains(resp, 'Hirz Calligraphy & Ritual Certificate')
        self.assertContains(resp, "Men&#x27;s Silver Rings")
        self.assertContains(resp, 'Toman')
        self.assertContains(resp, 'id="language-switcher-btn"')
        self.assertContains(resp, 'value="fa"')
        self.assertContains(resp, 'action="/en/i18n/setlang/"')

    def test_language_switcher_redirects_preserving_path_and_query(self):
        # Switch Persian -> English on filtered catalog URL
        resp_en = self.client.post(
            reverse('set_language'),
            data={'language': 'en', 'next': '/products/?type=hirz'},
        )
        self.assertEqual(resp_en.status_code, 302)
        self.assertEqual(resp_en['Location'], '/en/products/?type=hirz')
        self.assertEqual(self.client.cookies['django_language'].value, 'en')

        # Switch English -> Persian on filtered catalog URL (using English page's form action)
        with translation.override('en'):
            en_set_lang_url = reverse('set_language')
        self.assertEqual(en_set_lang_url, '/en/i18n/setlang/')
        resp_fa = self.client.post(
            en_set_lang_url,
            data={'language': 'fa', 'next': '/en/products/?type=hirz'},
        )
        self.assertEqual(resp_fa.status_code, 302)
        self.assertEqual(resp_fa['Location'], '/products/?type=hirz')
        self.assertEqual(self.client.cookies['django_language'].value, 'fa')

    def test_english_catalog_search_and_detail_variants(self):
        with translation.override('en'):
            en_list_url = reverse('store:product_list')

        search_resp = self.client.get(en_list_url, {'q': 'turquoise'})
        self.assertEqual(search_resp.status_code, 200)
        self.assertGreaterEqual(search_resp.context['total_count'], 2)
        self.assertContains(search_resp, 'Nishapur')

        ring = Product.objects.filter(product_type=Product.ProductType.RING).first()
        with translation.override('en'):
            en_ring_url = ring.get_absolute_url()
        ring_resp = self.client.get(en_ring_url)
        self.assertEqual(ring_resp.status_code, 200)
        self.assertContains(ring_resp, 'Ring Size Guide')
        self.assertContains(ring_resp, 'Size 56')
        self.assertContains(ring_resp, 'Size 66')
        self.assertContains(ring_resp, ring.title_en)

        hirz = Product.objects.filter(product_type=Product.ProductType.HIRZ).first()
        with translation.override('en'):
            en_hirz_url = hirz.get_absolute_url()
        hirz_resp = self.client.get(en_hirz_url)
        self.assertEqual(hirz_resp.status_code, 200)
        self.assertContains(hirz_resp, 'Cylindrical silver case')
        self.assertContains(hirz_resp, 'Hand-stitched leather armlet')
        self.assertContains(hirz_resp, 'Unframed / rolled scroll')
        self.assertNotContains(hirz_resp, 'id="size-guide-title"')

    def test_bilingual_session_cart_cross_language_display(self):
        ring = Product.objects.filter(product_type=Product.ProductType.RING, stock__gt=0).first()
        hirz = Product.objects.filter(product_type=Product.ProductType.HIRZ, stock__gt=0).first()

        # Add ring while browsing in Persian
        self.client.post(
            reverse('store:add_to_cart'),
            data={'product_id': ring.id, 'quantity': 1, 'variant': 'سایز ۶۰'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        # Inspect cart context while browsing in English
        with translation.override('en'):
            en_home_url = reverse('store:home')
            en_add_url = reverse('store:add_to_cart')
        en_home_resp = self.client.get(en_home_url)
        cart_items = en_home_resp.context['cart_items']
        self.assertEqual(len(cart_items), 1)
        self.assertEqual(cart_items[0]['title'], ring.title_en)
        self.assertEqual(cart_items[0]['variant'], 'Size 60')
        self.assertTrue(cart_items[0]['url'].startswith('/en/products/'))

        # Add Hirz in English
        en_resp = self.client.post(
            en_add_url,
            data={'product_id': hirz.id, 'quantity': 1, 'variant': 'Hand-stitched leather armlet'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(en_resp.status_code, 200)
        payload = en_resp.json()
        self.assertTrue(payload['success'])
        self.assertIn('has been added to your cart', payload['message'])
        self.assertEqual(payload['cart_count'], 2)
