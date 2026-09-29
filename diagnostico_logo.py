import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from django.conf import settings
from horarios.models import ConfiguracionInstitucion

print("=" * 60)
print("DIAGNÓSTICO DEL LOGO")
print("=" * 60)

print(f"\nMEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"DEBUG: {settings.DEBUG}")

config = ConfiguracionInstitucion.get_solo()
print(f"\nNombre: {config.nombre_institucion}")
print(f"Logo (campo): {config.logo}")

if config.logo:
    print(f"\nlogo.name: {config.logo.name}")
    print(f"logo.url: {config.logo.url}")
    print(f"logo.path: {config.logo.path}")
    
    existe = os.path.exists(config.logo.path)
    print(f"¿Existe el archivo en logo.path?: {existe}")
    
    if existe:
        size = os.path.getsize(config.logo.path)
        print(f"Tamaño del archivo: {size} bytes")
    else:
        # Buscar el archivo en otras ubicaciones
        print("\nBuscando el archivo en otras ubicaciones...")
        posibles = [
            os.path.join(settings.BASE_DIR, 'media', config.logo.name),
            os.path.join(settings.BASE_DIR, config.logo.name),
            os.path.join(settings.BASE_DIR, 'media', 'institucion', os.path.basename(config.logo.name)),
            os.path.join(settings.BASE_DIR, 'institucion', os.path.basename(config.logo.name)),
        ]
        for p in posibles:
            if os.path.exists(p):
                print(f"✅ ENCONTRADO en: {p}")
            else:
                print(f"❌ No existe: {p}")

print("\n" + "=" * 60)
print("ARCHIVOS EN MEDIA_ROOT")
print("=" * 60)

if os.path.exists(settings.MEDIA_ROOT):
    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
        for f in files:
            ruta = os.path.join(root, f)
            print(f"  {ruta}")
else:
    print(f"❌ MEDIA_ROOT no existe: {settings.MEDIA_ROOT}")

print("\n" + "=" * 60)
print("ARCHIVOS EN BASE_DIR/institucion (ubicación vieja)")
print("=" * 60)

viejo = os.path.join(settings.BASE_DIR, 'institucion')
if os.path.exists(viejo):
    for root, dirs, files in os.walk(viejo):
        for f in files:
            print(f"  {os.path.join(root, f)}")
else:
    print(f"❌ No existe: {viejo}")