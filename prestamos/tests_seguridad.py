"""Pruebas de seguridad. Usan la base temporal de pruebas, no los datos reales."""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, Herramienta, Prestamo

CLAVE = 'clave-solo-para-pruebas'
CARGA_XSS = '<script>alert(1)</script>'


class SeguridadTests(TestCase):
    fixtures = ['datos_iniciales']

    @classmethod
    def setUpTestData(cls):
        cls.socio = User.objects.create_user('socio_prueba', password=CLAVE)
        cls.otro = User.objects.create_user('otro_prueba', password=CLAVE)
        cls.encargado = User.objects.create_user(
            'encargado_prueba', password=CLAVE, is_staff=True)
        cls.prestamo = Prestamo.objects.create(
            socio=cls.otro, herramienta_id=2, fecha_devolucion_esperada=timezone.localdate())

    def url(self, nombre, *args):
        return reverse(f'prestamos:{nombre}', args=args)

    def rutas_con_sesion(self):
        sin_id = ['inicio', 'catalogo', 'ver_solicitud', 'mis_prestamos', 'confirmar_solicitud']
        con_id = ['agregar_solicitud', 'quitar_solicitud', 'prestamo_detail', 'cancelar_prestamo']
        return [self.url(n) for n in sin_id] + [
            self.url(n, self.prestamo.pk) for n in con_id] + self.rutas_encargado()

    def rutas_encargado(self):
        sin_id = ['herramienta_list', 'herramienta_create', 'categoria_list',
                  'categoria_create', 'prestamo_list']
        con_id = ['herramienta_detail', 'herramienta_update', 'herramienta_delete',
                  'categoria_update', 'categoria_delete', 'activar_prestamo',
                  'devolver_prestamo']
        return [self.url(n) for n in sin_id] + [self.url(n, 1) for n in con_id]

    def foto(self):
        return [list(m.objects.order_by('pk').values())
                for m in (Categoria, Herramienta, Prestamo)]

    def test_anonimo_no_entra_a_ninguna_ruta(self):
        antes = self.foto()
        for ruta in self.rutas_con_sesion():
            for metodo in (self.client.get, self.client.post):
                respuesta = metodo(ruta)
                self.assertIn(respuesta.status_code, (302, 405), ruta)
                if respuesta.status_code == 302:
                    self.assertTrue(respuesta.url.startswith(self.url('login')), ruta)
        self.assertEqual(self.foto(), antes)

    def test_socio_no_usa_rutas_del_encargado(self):
        self.client.force_login(self.socio)
        antes = self.foto()
        for ruta in self.rutas_encargado():
            for metodo in (self.client.get, self.client.post):
                self.assertIn(metodo(ruta).status_code, (403, 405), ruta)
        self.assertEqual(self.foto(), antes)

    def test_socio_no_accede_a_prestamo_ajeno(self):
        self.client.force_login(self.socio)
        antes = self.foto()
        self.assertEqual(
            self.client.get(self.url('prestamo_detail', self.prestamo.pk)).status_code, 404)
        self.assertEqual(
            self.client.post(self.url('cancelar_prestamo', self.prestamo.pk)).status_code, 404)
        self.assertEqual(self.foto(), antes)

    def test_get_no_modifica_datos(self):
        self.client.force_login(self.encargado)
        antes = self.foto()
        for ruta in self.rutas_con_sesion():
            self.client.get(ruta)
        self.assertEqual(self.foto(), antes)

    def test_post_sin_token_csrf_es_rechazado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.encargado)
        antes = self.foto()
        rutas = self.rutas_con_sesion() + [self.url('login'), self.url('logout')]
        for ruta in rutas:
            self.assertEqual(cliente.post(ruta).status_code, 403, ruta)
        self.assertEqual(self.foto(), antes)

    def test_xss_se_muestra_escapado(self):
        Categoria.objects.filter(pk=1).update(nombre=CARGA_XSS, descripcion=CARGA_XSS)
        Herramienta.objects.filter(pk=1).update(nombre=CARGA_XSS)
        User.objects.filter(pk=self.encargado.pk).update(first_name=CARGA_XSS)
        self.client.force_login(self.encargado)
        # Pasa también por los mensajes y la solicitud en sesión.
        paginas = [self.client.post(self.url('agregar_solicitud', 1), follow=True)]
        paginas += [self.client.get(r) for r in (
            self.url('catalogo'), self.url('ver_solicitud'), self.url('herramienta_list'),
            self.url('herramienta_detail', 1), self.url('herramienta_update', 1),
            self.url('herramienta_delete', 1), self.url('categoria_list'),
            self.url('categoria_delete', 1))]
        paginas.append(self.client.get(self.url('herramienta_list'), {'q': '">' + CARGA_XSS}))
        for pagina in paginas:
            self.assertNotContains(pagina, CARGA_XSS)

    def test_inyeccion_sql_en_busqueda(self):
        self.client.force_login(self.encargado)
        for carga in ("' OR '1'='1", "'; DROP TABLE prestamos_herramienta; --", '%', '_'):
            respuesta = self.client.get(self.url('herramienta_list'), {'q': carga})
            self.assertEqual(respuesta.status_code, 200, carga)
            self.assertEqual(list(respuesta.context['herramienta_list']), [], carga)
        respuesta = self.client.get(self.url('herramienta_list'), {'categoria': '1 OR 1=1'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Herramienta.objects.count(), 15)

    def test_entradas_extremas_no_causan_error_500(self):
        self.client.force_login(self.encargado)
        enorme = '9' * 40
        for consulta in ({'categoria': enorme}, {'categoria': '-1'}, {'categoria': '²'},
                         {'q': 'a' * 3000}, {'q': '\x00'}):
            respuesta = self.client.get(self.url('herramienta_list'), consulta)
            self.assertEqual(respuesta.status_code, 200, str(consulta)[:60])
        self.assertEqual(self.client.get(f'/herramientas/{enorme}/').status_code, 404)
        self.assertEqual(self.client.post(f'/solicitud/agregar/{enorme}/').status_code, 404)

    def test_login_no_redirige_a_otro_sitio(self):
        for destino in ('https://sitio-externo.example/', '//sitio-externo.example/'):
            respuesta = Client().post(
                self.url('login'),
                {'username': 'socio_prueba', 'password': CLAVE, 'next': destino})
            self.assertRedirects(respuesta, self.url('inicio'), fetch_redirect_response=False)

    def test_sesion_cambia_al_entrar_y_muere_al_salir(self):
        sesion = self.client.session
        sesion['previa'] = 1
        sesion.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = sesion.session_key
        respuesta = self.client.post(
            self.url('login'), {'username': 'socio_prueba', 'password': CLAVE})
        cookie = respuesta.cookies[settings.SESSION_COOKIE_NAME]
        self.assertNotEqual(cookie.value, sesion.session_key)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.client.post(self.url('logout'))
        copia = Client()
        copia.cookies[settings.SESSION_COOKIE_NAME] = cookie.value
        self.assertEqual(copia.get(self.url('inicio')).status_code, 302)

    def test_socio_no_entra_al_admin_y_encargado_no_ve_modelos(self):
        self.client.force_login(self.socio)
        self.assertEqual(self.client.get('/admin/prestamos/herramienta/').status_code, 302)
        self.client.force_login(self.encargado)
        self.assertEqual(self.client.get('/admin/prestamos/herramienta/').status_code, 403)

    def test_contrasenas_no_se_guardan_en_texto_plano(self):
        guardada = User.objects.get(pk=self.socio.pk).password
        self.assertNotIn(CLAVE, guardada)
        self.assertTrue(guardada.startswith('pbkdf2_'))
