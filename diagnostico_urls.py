import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from django.urls import reverse

print("=" * 60)
print("DIAGNÓSTICO DE URLS DEL CALENDARIO")
print("=" * 60)

try:
    url = reverse('horarios:calendario')
    print(f"✅ calendario: {url}")
except Exception as e:
    print(f"❌ calendario: {e}")

try:
    url = reverse('horarios:evento_crear')
    print(f"✅ evento_crear: {url}")
except Exception as e:
    print(f"❌ evento_crear: {e}")

try:
    url = reverse('horarios:evento_editar', args=[1])
    print(f"✅ evento_editar: {url}")
except Exception as e:
    print(f"❌ evento_editar: {e}")

try:
    url = reverse('horarios:evento_eliminar', args=[1])
    print(f"✅ evento_eliminar: {url}")
except Exception as e:
    print(f"❌ evento_eliminar: {e}")

try:
    url = reverse('horarios:pdf_calendario')
    print(f"✅ pdf_calendario: {url}")
except Exception as e:
    print(f"❌ pdf_calendario: {e}")

print()
print("=" * 60)
print("EVENTOS EXISTENTES EN LA BD")
print("=" * 60)

from horarios.models import EventoCalendario

total = EventoCalendario.objects.count()
print(f"Total de eventos: {total}")
for ev in EventoCalendario.objects.all()[:5]:
    print(f"  ID {ev.id}: {ev.fecha} - {ev.titulo}")

print("=" * 60)