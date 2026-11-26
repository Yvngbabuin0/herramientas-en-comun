from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .mixins import SoloEncargadoMixin
from .models import Categoria, Herramienta, Prestamo


class VistaEncargado(SoloEncargadoMixin, View):
    def get(self, request):
        return HttpResponse('ok')


class AccesoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.socio = User.objects.create_user('socio_prueba', password='clave-de-prueba')
        cls.encargado = User.objects.create_user('encargado_prueba', is_staff=True)

    def test_inicio_exige_sesion(self):
        respuesta = self.client.get(reverse('prestamos:inicio'))
        self.assertRedirects(respuesta, f"{reverse('prestamos:login')}?next=/")

    def test_login_y_logout(self):
        respuesta = self.client.post(
            reverse('prestamos:login'),
            {'username': 'socio_prueba', 'password': 'clave-de-prueba'},
            follow=True,
        )
        self.assertContains(respuesta, 'socio_prueba')
        self.assertContains(respuesta, 'Cerrar sesión')
        self.assertNotContains(respuesta, reverse('admin:index'))
        respuesta = self.client.post(reverse('prestamos:logout'))
        self.assertRedirects(respuesta, reverse('prestamos:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_solo_encargado(self):
        vista = VistaEncargado.as_view()
        peticion = RequestFactory().get('/prueba/')
        peticion.user = AnonymousUser()
        self.assertEqual(vista(peticion).status_code, 302)
        peticion.user = self.socio
        with self.assertRaises(PermissionDenied):
            vista(peticion)
        peticion.user = self.encargado
        self.assertEqual(vista(peticion).status_code, 200)

    def test_sesion_dura_30_minutos(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 1800)
        self.client.post(
            reverse('prestamos:login'),
            {'username': 'socio_prueba', 'password': 'clave-de-prueba'},
        )
        self.assertEqual(self.client.session.get_expiry_age(), 1800)


class CrudTests(TestCase):
    fixtures = ['datos_iniciales']

    @classmethod
    def setUpTestData(cls):
        cls.socio = User.objects.create_user('socio_prueba')
        cls.encargado = User.objects.create_user('encargado_prueba', is_staff=True)

    def setUp(self):
        self.client.force_login(self.encargado)

    def url(self, nombre, *args):
        return reverse(f'prestamos:{nombre}', args=args)

    def datos(self, **cambios):
        return {
            'codigo': 'HER-100', 'nombre': 'Nivel', 'categoria': 1, 'estado': 'bueno',
            'disponible': 'on', 'fecha_ingreso': '2026-01-01', **cambios,
        }

    def test_solo_encargado(self):
        rutas = [self.url(n) for n in (
            'herramienta_list', 'herramienta_create', 'categoria_list', 'categoria_create')]
        rutas += [self.url(n, 1) for n in (
            'herramienta_detail', 'herramienta_update', 'herramienta_delete',
            'categoria_update', 'categoria_delete')]
        for ruta in rutas:
            self.client.force_login(self.encargado)
            self.assertEqual(self.client.get(ruta).status_code, 200, ruta)
            self.client.force_login(self.socio)
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)
            self.assertEqual(self.client.post(ruta).status_code in (403, 405), True, ruta)
            self.client.logout()
            self.assertEqual(self.client.get(ruta).status_code, 302, ruta)

    def test_fixture_cumple_el_formato(self):
        for codigo in Herramienta.objects.values_list('codigo', flat=True):
            self.assertRegex(codigo, r'^HER-[0-9]{3}$')

    def test_formato_del_codigo(self):
        for codigo in ('MAN-001', 'HER-01', 'HER-0001', 'her-100', 'HER-ABC', 'XHER-100'):
            respuesta = self.client.post(self.url('herramienta_create'), self.datos(codigo=codigo))
            self.assertContains(respuesta, 'El código debe tener el formato HER-000')
            self.assertContains(respuesta, 'No se pudo guardar')
        self.assertEqual(Herramienta.objects.count(), 15)

    def test_buscar_y_filtrar(self):
        def codigos(consulta):
            respuesta = self.client.get(self.url('herramienta_list') + consulta)
            return [h.codigo for h in respuesta.context['herramienta_list']]
        self.assertEqual(codigos('?q=TALADRO'), ['HER-006'])
        self.assertEqual(len(codigos('?categoria=3')), 5)
        self.assertEqual(codigos('?q=taladro&categoria=3'), [])
        self.assertEqual(len(codigos('?categoria=abc')), 15)
        respuesta = self.client.get(self.url('herramienta_list') + '?categoria=3')
        self.assertContains(respuesta, '<option value="3" selected>')

    def test_detalle_inexistente(self):
        self.assertEqual(self.client.get(self.url('herramienta_detail', 999)).status_code, 404)

    def test_crear_editar_eliminar_herramienta(self):
        respuesta = self.client.post(self.url('herramienta_create'), self.datos(), follow=True)
        self.assertRedirects(respuesta, self.url('herramienta_list'))
        self.assertContains(respuesta, 'se creó correctamente')
        pk = Herramienta.objects.get(codigo='HER-100').pk
        respuesta = self.client.get(self.url('herramienta_update', pk))
        self.assertContains(respuesta, 'value="2026-01-01"')
        self.assertContains(respuesta, 'value="HER-100"')
        respuesta = self.client.post(
            self.url('herramienta_update', pk), self.datos(nombre='Nivel láser'), follow=True)
        self.assertContains(respuesta, 'se actualizó correctamente')
        self.client.get(self.url('herramienta_delete', pk))
        self.assertTrue(Herramienta.objects.filter(pk=pk).exists())
        self.assertEqual(self.client.delete(self.url('herramienta_delete', pk)).status_code, 405)
        respuesta = self.client.post(self.url('herramienta_delete', pk), follow=True)
        self.assertContains(respuesta, 'se eliminó correctamente')
        self.assertFalse(Herramienta.objects.filter(pk=pk).exists())

    def test_crear_editar_eliminar_categoria(self):
        datos = {'nombre': 'Pintura', 'descripcion': 'Brochas y rodillos.'}
        respuesta = self.client.post(self.url('categoria_create'), datos, follow=True)
        self.assertContains(respuesta, 'se creó correctamente')
        respuesta = self.client.post(self.url('categoria_create'), datos)
        self.assertContains(respuesta, 'No se pudo guardar')
        pk = Categoria.objects.get(nombre='Pintura').pk
        respuesta = self.client.post(
            self.url('categoria_update', pk), {**datos, 'nombre': 'Pinturas'}, follow=True)
        self.assertContains(respuesta, 'se actualizó correctamente')
        self.client.get(self.url('categoria_delete', pk))
        self.assertTrue(Categoria.objects.filter(pk=pk).exists())
        respuesta = self.client.post(self.url('categoria_delete', pk), follow=True)
        self.assertContains(respuesta, 'se eliminó correctamente')
        self.assertFalse(Categoria.objects.filter(pk=pk).exists())

    def test_eliminar_protegido(self):
        respuesta = self.client.post(self.url('categoria_delete', 1), follow=True)
        self.assertContains(respuesta, 'tiene herramientas asociadas')
        self.assertNotContains(respuesta, 'se eliminó correctamente')
        self.assertTrue(Categoria.objects.filter(pk=1).exists())
        Prestamo.objects.create(
            socio=self.socio, herramienta_id=1, fecha_devolucion_esperada='2026-12-01')
        respuesta = self.client.post(self.url('herramienta_delete', 1), follow=True)
        self.assertContains(respuesta, 'tiene préstamos registrados')
        self.assertTrue(Herramienta.objects.filter(pk=1).exists())


class SolicitudTests(TestCase):
    fixtures = ['datos_iniciales']

    @classmethod
    def setUpTestData(cls):
        cls.socio = User.objects.create_user('socio_prueba')
        cls.otro = User.objects.create_user('otro_prueba')

    def setUp(self):
        self.client.force_login(self.socio)

    def post(self, nombre, *args):
        return self.client.post(reverse(f'prestamos:{nombre}', args=args), follow=True)

    def solicitud(self):
        return self.client.session.get('solicitud', [])

    def test_catalogo_solo_prestables(self):
        Herramienta.objects.filter(pk=1).update(disponible=False)
        # En reparación pero marcada disponible: tampoco debe aparecer.
        Herramienta.objects.filter(pk=7).update(disponible=True)
        respuesta = self.client.get(reverse('prestamos:catalogo'))
        ids = {h.pk for h in respuesta.context['herramientas']}
        self.assertEqual(ids, set(range(1, 16)) - {1, 7, 15})
        self.assertContains(respuesta, 'Agregar a solicitud', count=12)

    def test_solo_post_y_con_sesion(self):
        rutas = [reverse('prestamos:agregar_solicitud', args=[1]),
                 reverse('prestamos:quitar_solicitud', args=[1]),
                 reverse('prestamos:confirmar_solicitud')]
        for ruta in rutas:
            self.assertEqual(self.client.get(ruta).status_code, 405, ruta)
        self.client.logout()
        for ruta in rutas:
            self.assertEqual(self.client.post(ruta).status_code, 302, ruta)
        for nombre in ('catalogo', 'ver_solicitud', 'mis_prestamos'):
            self.assertEqual(self.client.get(reverse(f'prestamos:{nombre}')).status_code, 302)
        self.assertFalse(Prestamo.objects.exists())

    def test_agregar_sin_repetir_y_maximo_tres(self):
        self.post('agregar_solicitud', 1)
        self.assertContains(self.post('agregar_solicitud', 1), 'ya está en tu solicitud')
        self.post('agregar_solicitud', 2)
        self.assertContains(self.post('agregar_solicitud', 3), 'Mi solicitud (3)')
        self.assertContains(self.post('agregar_solicitud', 4), 'más de 3 herramientas')
        self.assertEqual(self.solicitud(), [1, 2, 3])

    def test_agregar_no_disponible_o_inexistente(self):
        self.assertContains(self.post('agregar_solicitud', 7), 'no está disponible')
        self.assertEqual(self.post('agregar_solicitud', 999).status_code, 404)
        self.assertEqual(self.solicitud(), [])

    def test_ver_y_quitar(self):
        self.post('agregar_solicitud', 1)
        self.post('agregar_solicitud', 2)
        respuesta = self.client.get(reverse('prestamos:ver_solicitud'))
        self.assertEqual([h.pk for h in respuesta.context['herramientas']], [1, 2])
        self.assertContains(self.post('quitar_solicitud', 1), 'Mi solicitud (1)')
        self.assertEqual(self.solicitud(), [2])
        Herramienta.objects.filter(pk=2).delete()
        self.assertContains(
            self.client.get(reverse('prestamos:ver_solicitud')), 'Mi solicitud (0)')
        self.assertEqual(self.solicitud(), [])

    def test_confirmar(self):
        self.post('agregar_solicitud', 1)
        self.post('agregar_solicitud', 2)
        respuesta = self.post('confirmar_solicitud')
        self.assertRedirects(respuesta, reverse('prestamos:mis_prestamos'))
        self.assertContains(respuesta, 'Solicitud enviada')
        self.assertContains(respuesta, 'Mi solicitud (0)')
        self.assertNotIn('solicitud', self.client.session)
        hoy = timezone.localdate()
        self.assertEqual(Prestamo.objects.filter(
            socio=self.socio, estado='pendiente', fecha_solicitud=hoy,
            fecha_devolucion_esperada=hoy + timedelta(days=7)).count(), 2)
        self.assertFalse(Herramienta.objects.filter(pk__in=[1, 2], disponible=True).exists())

    def test_confirmar_verifica_de_nuevo(self):
        for pk in (1, 2, 3):
            self.post('agregar_solicitud', pk)
        Herramienta.objects.filter(pk=1).update(disponible=False)
        Herramienta.objects.filter(pk=2).update(estado='en_reparacion')
        respuesta = self.post('confirmar_solicitud')
        self.assertContains(respuesta, 'Ya no estaban disponibles')
        self.assertEqual(list(Prestamo.objects.values_list('herramienta_id', flat=True)), [3])
        self.assertNotIn('solicitud', self.client.session)

    def test_confirmar_vacia_y_prestamos_propios(self):
        self.assertContains(self.post('confirmar_solicitud'), 'solicitud está vacía')
        Prestamo.objects.create(
            socio=self.otro, herramienta_id=1, fecha_devolucion_esperada=timezone.localdate())
        respuesta = self.client.get(reverse('prestamos:mis_prestamos'))
        self.assertEqual(list(respuesta.context['prestamos']), [])
