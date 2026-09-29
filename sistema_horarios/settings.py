import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET_KEY desde variable de entorno (en local usa una por defecto)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-1234567890')

# DEBUG: False en producción, True en local (por defecto)
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ALLOWED_HOSTS: incluye localhost y el dominio de Render
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.ngrok-free.app',
    '.ngrok-free.dev',
    '.onrender.com',  # Dominio de Render
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok-free.dev',
    'https://*.onrender.com',  # Dominio de Render
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'horarios',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ← NUEVO: sirve archivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sistema_horarios.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'horarios.context_processors.config_institucion',
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema_horarios.wsgi.application'

# BASE DE DATOS:
# En producción (Render), leerá la variable DATABASE_URL (que apunta a Neon).
# En local, usará PostgreSQL local con tus credenciales.
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://postgres:diablo77@localhost:5432/controlescolar',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Mexico_City'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

# STATICFILES_DIRS: solo en desarrollo
if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / 'static']

# STATIC_ROOT: carpeta donde collectstatic guardará los archivos
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Almacenamiento de archivos estáticos con WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'horarios:login'
LOGIN_REDIRECT_URL = 'horarios:dashboard'
LOGOUT_REDIRECT_URL = 'horarios:login'