from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='comp-sys-home')
]