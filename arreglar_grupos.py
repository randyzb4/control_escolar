import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import Grupo

# Mapeo: nombre actual → nombre correcto
mapeo = {
    '1 "A"': '1º A',
    '1 "B"': '1º B',
    '2 "A"': '2º A',
    '2 "B"': '2º B',
    '3 "A"': '3º A',
    '3 "B"': '3º B',
}

for viejo, nuevo in mapeo.items():
    try:
        g = Grupo.objects.get(nombre=viejo)
        g.nombre = nuevo
        g.save()
        print(f"✅ [{viejo}] → [{nuevo}]")
    except Grupo.DoesNotExist:
        print(f"⚠️  No existe: [{viejo}]")

print()
print("=" * 60)
print("GRUPOS DESPUÉS DE LA CORRECCIÓN:")
print("=" * 60)
for g in Grupo.objects.all().order_by('nombre'):
    print(f"ID: {g.id} | Nombre: [{g.nombre}]")