from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView, View,
)

from .forms import CategoriaForm, HerramientaForm
from .mixins import SoloEncargadoMixin
from .models import Categoria, Herramienta, Prestamo

MAXIMO_SOLICITUD = 3
DIAS_PRESTAMO = 7


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


# Solicitud de préstamo (como un carrito, guardada en la sesión)

def herramientas_prestables():
    return Herramienta.objects.filter(disponible=True).exclude(
        estado=Herramienta.Estado.EN_REPARACION,
    )


@login_required
def catalogo(request):
    return render(request, 'prestamos/catalogo.html', {
        'herramientas': herramientas_prestables().select_related('categoria'),
        'solicitud': request.session.get('solicitud', []),
    })


@login_required
@require_POST
def agregar_solicitud(request, id):
    herramienta = get_object_or_404(Herramienta, pk=id)
    solicitud = request.session.get('solicitud', [])

    if id in solicitud:
        messages.error(request, f'«{herramienta.nombre}» ya está en tu solicitud.')
    elif len(solicitud) >= MAXIMO_SOLICITUD:
        messages.error(
            request, f'No puedes solicitar más de {MAXIMO_SOLICITUD} herramientas.')
    elif not herramientas_prestables().filter(pk=id).exists():
        messages.error(request, f'«{herramienta.nombre}» no está disponible.')
    else:
        request.session['solicitud'] = solicitud + [id]
        messages.success(request, f'«{herramienta.nombre}» se agregó a tu solicitud.')
    return redirect('prestamos:catalogo')


@login_required
def ver_solicitud(request):
    ids = request.session.get('solicitud', [])
    herramientas = Herramienta.objects.filter(id__in=ids).select_related('categoria')

    # Si el encargado eliminó una herramienta, se saca de la sesión para no contarla.
    existentes = {h.id for h in herramientas}
    if len(existentes) < len(ids):
        request.session['solicitud'] = [i for i in ids if i in existentes]

    return render(request, 'prestamos/solicitud.html', {'herramientas': herramientas})


@login_required
@require_POST
def quitar_solicitud(request, id):
    solicitud = request.session.get('solicitud', [])
    if id in solicitud:
        solicitud.remove(id)
        # Al cambiar la lista sin reasignarla, hay que avisar que la sesión cambió.
        request.session.modified = True
        messages.success(request, 'La herramienta se quitó de tu solicitud.')
    else:
        messages.error(request, 'Esa herramienta no estaba en tu solicitud.')
    return redirect('prestamos:ver_solicitud')


@login_required
@require_POST
def confirmar_solicitud(request):
    ids = request.session.get('solicitud', [])
    if not ids:
        messages.error(request, 'Tu solicitud está vacía.')
        return redirect('prestamos:ver_solicitud')

    hoy = timezone.localdate()
    creados = 0
    rechazadas = []
    with transaction.atomic():
        # select_for_update bloquea las filas: dos socios no pueden llevarse la misma.
        for herramienta in Herramienta.objects.select_for_update().filter(id__in=ids):
            if (not herramienta.disponible
                    or herramienta.estado == Herramienta.Estado.EN_REPARACION):
                rechazadas.append(herramienta.nombre)
                continue
            Prestamo.objects.create(
                socio=request.user,
                herramienta=herramienta,
                fecha_solicitud=hoy,
                fecha_devolucion_esperada=hoy + timedelta(days=DIAS_PRESTAMO),
                estado=Prestamo.Estado.PENDIENTE,
            )
            herramienta.disponible = False
            herramienta.save(update_fields=['disponible'])
            creados += 1

    del request.session['solicitud']

    if rechazadas:
        messages.error(
            request, 'Ya no estaban disponibles: ' + ', '.join(rechazadas) + '.')
    if creados:
        messages.success(request, f'Solicitud enviada. Préstamos pendientes creados: {creados}.')
    else:
        messages.error(request, 'No se creó ningún préstamo.')
    return redirect('prestamos:mis_prestamos')


@login_required
def mis_prestamos(request):
    prestamos = Prestamo.objects.filter(socio=request.user).select_related('herramienta')
    return render(request, 'prestamos/mis_prestamos.html', {'prestamos': prestamos})


@login_required
def prestamo_detail(request, id):
    # Al filtrar por socio, el id de un préstamo ajeno responde 404.
    prestamo = get_object_or_404(
        Prestamo.objects.select_related('herramienta'), pk=id, socio=request.user,
    )
    return render(request, 'prestamos/prestamo_detail.html', {'prestamo': prestamo})


def liberar_herramienta(herramienta_id):
    """Deja la herramienta disponible si no tiene otro préstamo pendiente o activo."""
    abiertos = Prestamo.objects.filter(
        herramienta_id=herramienta_id,
        estado__in=[Prestamo.Estado.PENDIENTE, Prestamo.Estado.ACTIVO],
    )
    if not abiertos.exists():
        Herramienta.objects.filter(pk=herramienta_id).update(disponible=True)


@login_required
@require_POST
def cancelar_prestamo(request, id):
    with transaction.atomic():
        prestamo = get_object_or_404(
            Prestamo.objects.select_for_update(), pk=id, socio=request.user,
        )
        if prestamo.estado != Prestamo.Estado.PENDIENTE:
            messages.error(request, 'Solo puedes cancelar préstamos pendientes.')
        else:
            prestamo.estado = Prestamo.Estado.CANCELADO
            prestamo.save(update_fields=['estado'])
            liberar_herramienta(prestamo.herramienta_id)
            messages.success(request, 'El préstamo se canceló correctamente.')
    return redirect('prestamos:mis_prestamos')


# Gestión de préstamos (encargado)

class PrestamoListView(SoloEncargadoMixin, ListView):
    model = Prestamo

    def get_queryset(self):
        return super().get_queryset().select_related('socio', 'herramienta')


class ActivarPrestamoView(SoloEncargadoMixin, View):
    http_method_names = ['post']

    def post(self, request, id):
        with transaction.atomic():
            prestamo = get_object_or_404(Prestamo.objects.select_for_update(), pk=id)
            if prestamo.estado != Prestamo.Estado.PENDIENTE:
                messages.error(request, 'Solo se pueden activar préstamos pendientes.')
            else:
                prestamo.estado = Prestamo.Estado.ACTIVO
                prestamo.save(update_fields=['estado'])
                messages.success(request, 'El préstamo se activó correctamente.')
        return redirect('prestamos:prestamo_list')


class DevolverPrestamoView(SoloEncargadoMixin, View):
    http_method_names = ['post']

    def post(self, request, id):
        with transaction.atomic():
            prestamo = get_object_or_404(Prestamo.objects.select_for_update(), pk=id)
            if prestamo.estado != Prestamo.Estado.ACTIVO:
                messages.error(
                    request, 'Solo se puede registrar la devolución de préstamos activos.')
            else:
                prestamo.estado = Prestamo.Estado.DEVUELTO
                prestamo.fecha_devolucion_real = timezone.localdate()
                prestamo.save(update_fields=['estado', 'fecha_devolucion_real'])
                liberar_herramienta(prestamo.herramienta_id)
                messages.success(request, 'La devolución se registró correctamente.')
        return redirect('prestamos:prestamo_list')
