from django import forms
from .models import Incidencia


class IncidenciaForm(forms.ModelForm):
    class Meta:
        model = Incidencia
        fields = ['fecha', 'alumno', 'grupo_materia', 'tipo_reporte', 'resumen']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'alumno': forms.Select(attrs={'class': 'form-select'}),
            'grupo_materia': forms.Select(attrs={'class': 'form-select'}),
            'tipo_reporte': forms.Select(attrs={'class': 'form-select'}),
            'resumen': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
        labels = {
            'fecha': 'Fecha',
            'alumno': 'Alumno',
            'grupo_materia': 'Grupo y Materia',
            'tipo_reporte': 'Tipo de reporte',
            'resumen': 'Resumen del reporte',
        }