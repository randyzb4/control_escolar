import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from django.template.loader import render_to_string
from xhtml2pdf import pisa
from horarios.models import ConfiguracionInstitucion

config = ConfiguracionInstitucion.get_solo()

# HTML mínimo de prueba
html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Prueba de Logo</h1>
    <p>Nombre: {config.nombre_institucion}</p>
    <p>Path: {config.logo.path if config.logo else 'Sin logo'}</p>
    <p>Existe: {os.path.exists(config.logo.path) if config.logo else False}</p>
    <img src="{config.logo.path}" style="max-height: 100px;" alt="Logo">
</body>
</html>
"""

# Generar PDF
with open('test_logo.pdf', 'wb') as f:
    pisa_status = pisa.CreatePDF(html, dest=f)
    if pisa_status.err:
        print(f"❌ Error: {pisa_status.err}")
    else:
        print("✅ PDF generado: test_logo.pdf")

print(f"\nRuta esperada: {os.path.abspath('test_logo.pdf')}")
print(f"¿Existe?: {os.path.exists('test_logo.pdf')}")
if os.path.exists('test_logo.pdf'):
    print(f"Tamaño: {os.path.getsize('test_logo.pdf')} bytes")