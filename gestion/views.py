from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import DocumentoForm
from .models import Documento # <--- Importamos el modelo para buscar
from .tasks import procesar_imagen_ia  #<--- 1. importamos la tare
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from .models import Documento

def lista_documentos(request):
    # 1. Obtener lo que el usuario escribió en la cajita de búsqueda
    query = request.GET.get('q') 

    # 2. Empezamos con todos los documentos
    documentos = Documento.objects.all().order_by('-id')

    # 3. Si el usuario escribió algo, filtramos
    if query:
        documentos = documentos.filter(
            # Busca si el texto coincide con algún TAG (JSON)
            Q(tags_ia__icontains=query) |  
            # O (el símbolo | significa OR)
            # Busca si el texto está dentro del contenido leído por Textract
            Q(texto_detectado__icontains=query) 
        )

    context = {
        'documentos': documentos,
        'query': query  # Para mantener el texto en la cajita después de buscar
    }
    return render(request, 'gestion/lista_documentos.html', context)

@login_required
def subir_archivo_view(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            # No guardamos todavía en la BD
            documento = form.save(commit=False)
            # Le asignamos el usuario conectado
            documento.usuario = request.user 
            if not documento.titulo: 
                documento.titulo = request.FILES['archivo'].name
            # Ahora sí guardamos  ( se genera el id)
            documento.save()
           
            
            #<----2. diaparamos la tarea a celery
            # le pasamos solo el id, no el objeto entero ( regla de oro de celery)
            procesar_imagen_ia.delay(documento.id)

            return redirect('subir_archivo')
   
    else:
        form = DocumentoForm()

    # FILTRO MÁGICO: Trae solo los documentos donde usuario = usuario_actual
    mis_documentos = Documento.objects.filter(usuario=request.user).order_by('-fecha')

    return render(request, 'gestion/subir_archivo.html', {
        'form': form, 
        'mis_documentos': mis_documentos # Enviamos la lista al HTML
    })


def eliminar_documento(request, documento_id):
    # 1. Buscamos el documento o damos error 404 si no existe
    documento = get_object_or_404(Documento, id=documento_id)
    
    # 2. (Opcional) Aquí podrías agregar lógica para borrar el archivo físico de S3
    # documento.archivo.delete() 
    
    # 3. Borramos el registro de la Base de Datos
    documento.delete()
    
    # 4. Volvemos a la lista
    return redirect('subir_archivo')
