from django import forms
from .models import Documento

class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ['titulo', 'archivo'] # Solo pedimos estos dos campos
        # Añadimos clases de Bootstrap para que se vea bien
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Campaña Verano 2025'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
        }
