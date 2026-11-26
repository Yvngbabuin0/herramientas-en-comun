from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
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
