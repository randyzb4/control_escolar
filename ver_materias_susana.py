import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import GrupoMateria, Grupo, Materia, Profesor
from django.contrib.auth.models import User

# Simular lo que hace la vista para Susana
u = User.objects.get(username='susana')
profesor = u.perfil.profesor
print(f"Usuario: {u.username}")
print(f"Profesor: {profesor.nombre}")
print()

# Grupos que imparte
grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
print("=" * 60)
print("GRUPOS QUE IMPARTE:")
print("=" * 60)
for g in grupos:
    print(f"  ID: {g.id} | {g.nombre}")
print()

# Simular selección de un grupo (el primero)
if grupos:
    grupo_sel = grupos[0]
    print(f"Simulando selección del grupo: {grupo_sel.nombre} (id={grupo_sel.id})")
    print()

    materias = Materia.objects.filter(
        grupomateria__grupo_id=grupo_sel.id,
        grupomateria__profesor=profesor
    ).distinct()

    print(f"Materias que devuelve la consulta: {materias.count()}")
    for m in materias:
        print(f"  - {m.nombre}")
else:
    print("⚠️  No hay grupos para este profesor")