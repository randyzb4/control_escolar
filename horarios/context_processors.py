from .models import ConfiguracionInstitucion

def config_institucion(request):
    try:
        config = ConfiguracionInstitucion.get_solo()
        return {'config_institucion': config}
    except Exception:
        return {'config_institucion': None}
