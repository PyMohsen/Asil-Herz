from django.urls import path

from . import views

app_name = 'store'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('products/', views.product_list_view, name='product_list'),
    path('products/<str:slug>/', views.product_detail_view, name='product_detail'),
    path('cart/add/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/remove/', views.remove_from_cart_view, name='remove_from_cart'),
]
