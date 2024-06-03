from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('get_author_pub_distribution/', views.get_author_pub_distribution, name='get_author_pub_distribution')
]
