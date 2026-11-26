# Bitácora de uso de IA

## 25/11/2026: diseño de la interfaz

**Herramienta:** Claude Code

### Prompt

> ahora necesito que me hagas un html para la web que sea funcional y simple, nada super elaborado con colores no llamativos, que sea acorde al contexto que te di. Ese prompt, guardalo en una junto con tu respuesta BITACORA_IA.md

### Respuesta

Apliqué un diseño simple a la aplicación, sin hacer commit. En vez de crear una página
suelta, lo integré en las plantillas de Django para que las pantallas sigan funcionando
con los datos reales.

- **Plantilla base** (`prestamos/templates/base.html`): tiene el HTML y el CSS comunes.
  Incluye un encabezado con el nombre de la Junta de Vecinos, el usuario conectado, el
  menú, los mensajes y un pie de página. Todas las pantallas de la aplicación la heredan;
  el admin de Django mantiene su propio diseño.
- **Colores:** verde apagado, blanco y gris cálido. Los mensajes de error usan un rojo suave.
- **Inicio:** ahora tiene accesos para pedir herramientas y revisar préstamos. El encargado
  ve además los accesos al inventario y a la gestión de préstamos.
- **Tablas y formularios:** tienen un estilo común. En el celular, las tablas se desplazan
  hacia los lados sin mover toda la página.
- **Corrección:** en el formulario de herramientas, la opción en inglés
  "Select an option" ahora dice "Selecciona una categoría".

No usa librerías, imágenes ni fuentes externas.

**Comprobaciones:** pasan las 27 pruebas. En el navegador, con el usuario `encargado`,
revisé el inicio, el listado y el formulario de herramientas, la confirmación para eliminar
una categoría y el catálogo en tamaño de celular. No revisé visualmente todas las pantallas
ni volví a entrar como `socio` después del cambio de diseño.

## 25/11/2026: pruebas de seguridad

**Herramienta:** Claude Code

### Prompt

> realiza pruebas de seguridad

El "no" respondía a la pregunta de si la bitácora era el ítem 3 del Punto 6.

### Respuesta

Se pidió realizar pruebas de seguridad. Las pruebas automáticas están en
`prestamos/tests_seguridad.py` y usan una base de datos temporal.

#### Pruebas automáticas: las 12 pasaron

| Prueba | Resultado |
|---|---|
| Usuario sin sesión en las rutas protegidas | Redirige al login o rechaza el método |
| Socio en rutas del encargado | Rechazado, sin cambios en los datos |
| Socio que intenta ver o cancelar un préstamo ajeno | Error 404 |
| Solicitudes `GET` a las rutas protegidas | No modifican categorías, herramientas ni préstamos |
| `POST` sin token CSRF, incluidos login y logout | Error 403 |
| XSS en nombres, descripción, usuario y buscador (páginas revisadas) | El código se muestra escapado |
| Inyección SQL en el buscador y el filtro | Las cargas probadas no alteran la consulta ni borran datos |
| Valores extremos en búsqueda, filtro e ids | Sin errores 500 en los casos probados |
| Redirección del login a un sitio externo | Bloqueada |
| Sesión | Cambia al iniciar sesión, es `HttpOnly` y `SameSite=Lax`, y deja de servir al salir |
| Acceso al admin | El socio no entra a los modelos; el encargado no tiene permisos sobre ellos |
| Almacenamiento de contraseñas | Guardadas con hash PBKDF2 |

#### Otras revisiones

- La `SECRET_KEY`, la clave de la base de datos y las claves de prueba actuales no
  aparecen en el historial de Git ni en los archivos pendientes de confirmar al momento
  de la revisión. El `.env` nunca se incluyó en Git.
- La base de datos del proyecto (puerto 3307) solo escucha en `127.0.0.1`.

#### Hallazgos pendientes (no se corrigieron)

1. **El login no limita los intentos fallidos.** Se hicieron 30 intentos seguidos y la
   aplicación respondió a todos sin bloquear ni frenar con un error. Permite probar claves
   por fuerza bruta.
2. **La aplicación usa el usuario `root` de la base de datos del proyecto.** Conviene
   crear un usuario con permisos solo sobre `herramientas_db`.
3. **La configuración es de desarrollo.** `manage.py check --deploy` advierte que
   `DEBUG` está activo, `ALLOWED_HOSTS` está vacío y faltan la redirección a HTTPS, HSTS
   y las cookies seguras. Debe corregirse antes de publicar la aplicación. También informa
   un error porque el correo usa un servicio solo para desarrollo.

#### Alcance

No se revisaron vulnerabilidades conocidas de las dependencias ni se hicieron pruebas de
carga, de red o una auditoría manual completa. Que estas pruebas pasen no garantiza que la
aplicación no tenga otras fallas.

Para repetir las pruebas automáticas:

```powershell
python manage.py test prestamos.tests_seguridad
```

### Prompt

> crea una vista para el socio que liste solo las herramientas disponibles y que no estén “En reparación”, cada una con un botón “Agregar a solicitud”.

### Respuesta simulada

Crearía la vista `catalogo`, protegida con `@login_required`. Para mostrar solo las
herramientas que se pueden pedir, filtraría las disponibles y excluiría las que están en
reparación:

```python
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
```

En el template `catalogo.html` mostraría una tabla y, en cada fila, un formulario con el
botón. Usaría `POST` y el token CSRF porque agregar una herramienta modifica la sesión:

```django
<form method="post" action="{% url 'prestamos:agregar_solicitud' herramienta.id %}">
    {% csrf_token %}
    <button type="submit">Agregar a solicitud</button>
</form>
```

También agregaría la ruta `catalogo/` con el nombre `catalogo`, la ruta de
`agregar_solicitud` que usa el botón y un enlace al catálogo en el menú.
