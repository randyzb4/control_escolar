import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import ConfiguracionInstitucion

print("=" * 60)
print("CONFIGURACIÓN INSTITUCIONAL")
print("=" * 60)

try:
    config = ConfiguracionInstitucion.get_solo()
    print(f"ID: {config.id}")
    print(f"Nombre: [{config.nombre_institucion}]")
    print(f"Logo: {config.logo}")
    print(f"Logo URL: {config.logo_url() if hasattr(config, 'logo_url') else 'N/A'}")
    if config.logo:
        print(f"Logo path absoluto: {config.logo.path}")
        print(f"¿Existe el archivo?: {os.path.exists(config.logo.path)}")
    print(f"Ciclo escolar: {config.ciclo_escolar}")
except Exception as e:
    print(f"Error: {e}")

print("=" * 60)