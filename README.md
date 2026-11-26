# Herramientas en Común

Aplicación web en Django para que la Junta de Vecinos Villa Los Aromos administre
el inventario de herramientas y sus préstamos.

## Requisitos

- Python 3.12 o superior
- MariaDB o MySQL (versión compatible con Django 6.1)

## Cómo ejecutarlo (Windows, PowerShell)

Ejecuta los comandos desde la carpeta del proyecto.

### 1. Entorno virtual y dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Variables de entorno

```powershell
Copy-Item .env.example .env
```

Abre `.env` y completa:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | Una clave propia. Puedes generarla con el comando de abajo |
| `DEBUG` | `True` para desarrollo |
| `DB_NAME` | `herramientas_db` |
| `DB_USER`, `DB_PASSWORD` | Tu usuario y contraseña de la base de datos |
| `DB_HOST`, `DB_PORT` | Servidor y puerto (normalmente `127.0.0.1` y `3306`) |

```powershell
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

El archivo `.env` no se sube al repositorio.

### 3. Base de datos

En la consola de MariaDB o MySQL:

```sql
CREATE DATABASE herramientas_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Luego crea las tablas y carga los datos de prueba (3 categorías y 15 herramientas):

```powershell
python manage.py migrate
```

```powershell
python manage.py loaddata datos_iniciales
```

> Cargar de nuevo los datos de prueba sobrescribe las categorías y herramientas
> que tengan los mismos identificadores.

### 4. Usuarios de prueba

| Usuario | Rol | Permisos en la aplicación |
|---|---|---|
| `admin` | Superusuario | Todo, incluido el admin de Django |
| `encargado` | Encargado (`is_staff`) | Herramientas, categorías y todos los préstamos |
| `socio` | Socio | Catálogo, solicitud y sus propios préstamos |

El fixture no incluye usuarios. En una instalación nueva, créalos así:

```powershell
python manage.py createsuperuser --username admin
```

```powershell
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_user('encargado', is_staff=True); User.objects.create_user('socio')"
```

```powershell
python manage.py changepassword encargado
```

```powershell
python manage.py changepassword socio
```

Cada comando pide la contraseña, así que ninguna queda guardada en el repositorio.

El usuario `encargado` no tiene permisos sobre los modelos en el admin de Django:
gestiona todo desde las páginas de la aplicación.

### 5. Servidor

```powershell
python manage.py runserver
```

Abre <http://127.0.0.1:8000/> e inicia sesión.

## Cómo se usa

**Socio**

1. En **Catálogo**, agrega hasta 3 herramientas a la solicitud.
2. En **Mi solicitud**, revisa y confirma. Los préstamos quedan *Pendientes*, con
   devolución esperada a 7 días.
3. En **Mis préstamos**, revisa tus préstamos y cancela los *Pendientes*.

**Encargado**

- **Herramientas** y **Categorías**: crear, editar y eliminar. El código de una
  herramienta tiene el formato `HER-000`.
- **Todos los préstamos**: activar los *Pendientes* y registrar la devolución de
  los *Activos*.

Estados de un préstamo: *Pendiente* → *Activo* → *Devuelto*, o
*Pendiente* → *Cancelado*.

La sesión expira a los 30 minutos.

## Pruebas

```powershell
python manage.py test prestamos
```

El usuario de la base de datos necesita permiso para crear la base temporal de
pruebas (`test_herramientas_db`).
