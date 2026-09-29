import os
import django
import base64

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from xhtml2pdf import pisa
from horarios.models import ConfiguracionInstitucion

config = ConfiguracionInstitucion.get_solo()

if not config.logo:
    print("No hay logo configurado")
    exit()

print("=" * 60)
print("TEST DE LOGO DIRECTO")
print("=" * 60)
print(f"Nombre: {config.nombre_institucion}")
print(f"Logo path: {config.logo.path}")
print(f"Existe: {os.path.exists(config.logo.path)}")

with open(config.logo.path, 'rb') as f:
    data = f.read()
    print(f"Tamaño: {len(data)} bytes")
    b64 = base64.b64encode(data).decode('utf-8')

ext = config.logo.name.lower().split('.')[-1]
mime = 'image/png' if ext == 'png' else 'image/jpeg'

html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>
    <h1>Test de logo base64</h1>
    <p>Nombre: {config.nombre_institucion}</p>
    <img src="data:{mime};base64,{b64}" style="max-height: 100px;">
    <p>Fin del test.</p>
</body>
</html>
"""

with open('test_logo_directo.pdf', 'wb') as f:
    status = pisa.CreatePDF(html, dest=f)
    if status.err:
        print(f"ERROR: {status.err}")
    else:
        print("PDF generado: test_logo_directo.pdf")

if os.path.exists('test_logo_directo.pdf'):
    print(f"Tamaño del PDF: {os.path.getsize('test_logo_directo.pdf')} bytes")