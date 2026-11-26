from django.conf import settings
from django.db import models
from django.utils import timezone


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField('descripción')

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Herramienta(models.Model):
    class Estado(models.TextChoices):
        BUENO = 'bueno', 'Bueno'
        REGULAR = 'regular', 'Regular'
        EN_REPARACION = 'en_reparacion', 'En reparación'

    codigo = models.CharField('código', max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='herramientas',
        verbose_name='categoría',
    )
    estado = models.CharField(max_length=15, choices=Estado, default=Estado.BUENO)
    disponible = models.BooleanField(default=True)
    fecha_ingreso = models.DateField('fecha de ingreso', default=timezone.localdate)

    class Meta:
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Prestamo(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ACTIVO = 'activo', 'Activo'
        DEVUELTO = 'devuelto', 'Devuelto'
        CANCELADO = 'cancelado', 'Cancelado'

    socio = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='prestamos',
    )
    herramienta = models.ForeignKey(
        Herramienta, on_delete=models.PROTECT, related_name='prestamos',
    )
    fecha_solicitud = models.DateField('fecha de solicitud', default=timezone.localdate)
    fecha_devolucion_esperada = models.DateField('fecha de devolución esperada')
    fecha_devolucion_real = models.DateField(
        'fecha de devolución real', null=True, blank=True,
    )
    estado = models.CharField(max_length=10, choices=Estado, default=Estado.PENDIENTE)

    class Meta:
        verbose_name = 'préstamo'
        ordering = ['-fecha_solicitud', '-pk']

    def __str__(self):
        return f'{self.herramienta} → {self.socio} ({self.get_estado_display()})'
