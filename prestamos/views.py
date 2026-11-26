from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import CategoriaForm, HerramientaForm
from .mixins import SoloEncargadoMixin
from .models import Categoria, Herramienta


@login_required
def inicio(request):
    return render(request, 'prestamos/inicio.html')


class GuardarMixin(SoloEncargadoMixin, SuccessMessageMixin):
    """Crear y editar: mensaje de éxito al guardar y de error si el formulario no es válido."""

    def form_invalid(self, form):
        messages.error(self.request, 'No se pudo guardar. Revisa los errores del formulario.')
        return super().form_invalid(form)


class EliminarMixin(SoloEncargadoMixin, SuccessMessageMixin):
    """GET muestra la confirmación; solo POST elimina."""

    http_method_names = ['get', 'post']
    mensaje_protegido = ''

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.mensaje_protegido)
            return redirect(self.success_url)


# Herramientas

class HerramientaListView(SoloEncargadoMixin, ListView):
    model = Herramienta

    def get_queryset(self):
        herramientas = super().get_queryset().select_related('categoria')
        busqueda = self.request.GET.get('q', '').strip()
        categoria = self.request.GET.get('categoria', '')
        if busqueda:
            herramientas = herramientas.filter(nombre__icontains=busqueda)
        if categoria.isdecimal():
            herramientas = herramientas.filter(categoria_id=categoria)
        return herramientas

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            categorias=Categoria.objects.all(),
            busqueda=self.request.GET.get('q', '').strip(),
            categoria_elegida=self.request.GET.get('categoria', ''),
            **kwargs,
        )


class HerramientaDetailView(SoloEncargadoMixin, DetailView):
    model = Herramienta

    def get_object(self, queryset=None):
        return get_object_or_404(
            Herramienta.objects.select_related('categoria'), pk=self.kwargs['pk'],
        )


class HerramientaCreateView(GuardarMixin, CreateView):
    model = Herramienta
    form_class = HerramientaForm
    success_url = reverse_lazy('prestamos:herramienta_list')
    success_message = 'La herramienta «%(nombre)s» se creó correctamente.'


class HerramientaUpdateView(GuardarMixin, UpdateView):
    # UpdateView entrega el formulario con instance=, es decir, precargado.
    model = Herramienta
    form_class = HerramientaForm
    success_url = reverse_lazy('prestamos:herramienta_list')
    success_message = 'La herramienta «%(nombre)s» se actualizó correctamente.'


class HerramientaDeleteView(EliminarMixin, DeleteView):
    model = Herramienta
    success_url = reverse_lazy('prestamos:herramienta_list')
    success_message = 'La herramienta se eliminó correctamente.'
    mensaje_protegido = 'No se puede eliminar la herramienta porque tiene préstamos registrados.'


# Categorías

class CategoriaListView(SoloEncargadoMixin, ListView):
    model = Categoria


class CategoriaCreateView(GuardarMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    success_url = reverse_lazy('prestamos:categoria_list')
    success_message = 'La categoría «%(nombre)s» se creó correctamente.'


class CategoriaUpdateView(GuardarMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    success_url = reverse_lazy('prestamos:categoria_list')
    success_message = 'La categoría «%(nombre)s» se actualizó correctamente.'


class CategoriaDeleteView(EliminarMixin, DeleteView):
    model = Categoria
    success_url = reverse_lazy('prestamos:categoria_list')
    success_message = 'La categoría se eliminó correctamente.'
    mensaje_protegido = 'No se puede eliminar la categoría porque tiene herramientas asociadas.'
