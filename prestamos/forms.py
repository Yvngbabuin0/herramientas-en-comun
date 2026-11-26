import re

from django import forms

from .models import Categoria, Herramienta


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']


class HerramientaForm(forms.ModelForm):
    class Meta:
        model = Herramienta
        fields = ['codigo', 'nombre', 'categoria', 'estado', 'disponible', 'fecha_ingreso']
        help_texts = {'codigo': 'Formato HER-000 (tres dígitos).'}
        widgets = {
            # El control de fecha del navegador solo acepta el formato AAAA-MM-DD.
            'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo']
        if not re.fullmatch(r'HER-[0-9]{3}', codigo):
            raise forms.ValidationError(
                'El código debe tener el formato HER-000 (tres dígitos).'
            )
        return codigo
