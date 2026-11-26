from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views import View

from .mixins import SoloEncargadoMixin


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
