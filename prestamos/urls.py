from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = 'prestamos'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('catalogo/', views.catalogo, name='catalogo'),
    path('solicitud/', views.ver_solicitud, name='ver_solicitud'),
    path('solicitud/agregar/<int:id>/', views.agregar_solicitud, name='agregar_solicitud'),
    path('solicitud/quitar/<int:id>/', views.quitar_solicitud, name='quitar_solicitud'),
    path('solicitud/confirmar/', views.confirmar_solicitud, name='confirmar_solicitud'),
    path('mis-prestamos/', views.mis_prestamos, name='mis_prestamos'),

    path('herramientas/', views.HerramientaListView.as_view(), name='herramienta_list'),
    path('herramientas/nueva/', views.HerramientaCreateView.as_view(), name='herramienta_create'),
    path('herramientas/<int:pk>/', views.HerramientaDetailView.as_view(), name='herramienta_detail'),
    path('herramientas/<int:pk>/editar/', views.HerramientaUpdateView.as_view(), name='herramienta_update'),
    path('herramientas/<int:pk>/eliminar/', views.HerramientaDeleteView.as_view(), name='herramienta_delete'),

    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),
    path('categorias/<int:pk>/eliminar/', views.CategoriaDeleteView.as_view(), name='categoria_delete'),
]
