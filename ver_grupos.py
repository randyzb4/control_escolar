import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import Grupo, Alumno

print("=" * 60)
print("GRUPOS REGISTRADOS")
print("=" * 60)

for g in Grupo.objects.all().order_by('nombre'):
    print(f"ID: {g.id} | Nombre: [{g.nombre}] | Longitud: {len(g.nombre)}")
    print(f"   Alumnos: {g.alumnos.count()}")
    print(f"   Caracteres: {[ord(c) for c in g.nombre]}")
    print()

print("=" * 60)
print(f"Total grupos: {Grupo.objects.count()}")
print(f"Total alumnos: {Alumno.objects.count()}")
print("=" * 60)