from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = 'prestamos'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
