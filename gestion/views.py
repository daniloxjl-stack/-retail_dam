from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import DocumentoForm
from .models import Documento
from .tasks import procesar_archivo_ia 
from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction # Importante para la estabilidad de Celery
import time
import random        
import boto3
import json      

# --- IMPORTS NUEVOS PARA BÚSQUEDA VECTORIAL ---
from pgvector.django import L2Distance

# --- CONFIGURACIÓN DEL CHATBOT ---
USA_BEDROCK = False 

# Configuración Cliente Bedrock (Para generar embeddings de búsqueda)
try:
    bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
except:
    bedrock_client = None

def generar_embedding_consulta(texto):
    """ Convierte la búsqueda del usuario en un Vector usando Titan """
    if not bedrock_client: return None
    try:
        body = json.dumps({"inputText": texto})
        response = bedrock_client.invoke_model(
            body=body,
            modelId="amazon.titan-embed-text-v1",
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding")
    except Exception as e:
        print(f"Error generando vector consulta: {e}")
        return None

@login_required
def lista_documentos(request):
    query = request.GET.get('q')
    
    # 1. Filtro base de privacidad
    documentos = Documento.objects.filter(usuario=request.user)

    if query:
        # --- A) INTENTO DE BÚSQUEDA VECTORIAL (Inteligente) ---
        vector_busqueda = generar_embedding_consulta(query)
        
        if vector_busqueda:
            # Si Bedrock funcionó, ordenamos por similitud semántica
            # (El más parecido tiene menor distancia)
            documentos = documentos.annotate(
                distancia=L2Distance('embedding', vector_busqueda)
            ).order_by('distancia')
        else:
            # --- B) FALLBACK: BÚSQUEDA CLÁSICA (Si falla la IA) ---
            documentos = documentos.filter(
                Q(tags_ia__icontains=query) |  
                Q(texto_detectado__icontains=query) |
                Q(titulo__icontains=query)
            ).order_by('-id')
    else:
        # Si no hay búsqueda, orden normal
        documentos = documentos.order_by('-id')

    context = {
        'documentos': documentos,
        'query': query
    }
    return render(request, 'gestion/lista_documentos.html', context)


@login_required
def subir_archivo_view(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.usuario = request.user
            
            if not documento.titulo:
                documento.titulo = request.FILES['archivo'].name
            
            documento.estado = 'pendiente'
            documento.save() 

            # USAMOS TRANSACTION PARA EVITAR ERRORES DE CARRERA
            transaction.on_commit(lambda: procesar_archivo_ia.delay(documento.id))

            return redirect('subir_archivo') 
    else:
        form = DocumentoForm()

    mis_documentos = Documento.objects.filter(usuario=request.user).order_by('-id')

    return render(request, 'gestion/subir_archivo.html', {
        'form': form, 
        'mis_documentos': mis_documentos
    })

def eliminar_documento(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id)
    # Seguridad extra: solo borrar si es del usuario
    if documento.usuario == request.user:
        documento.delete()
    return redirect('subir_archivo')


# ==============================================================================
#  API DEL CHATBOT (CEREBRO RAG) - SIN CAMBIOS
# ==============================================================================
@csrf_exempt
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        pregunta = data.get('pregunta', '').lower()
        
        response_data = {
            'texto': '',
            'acciones': [],
            'docs': []
        }

        # PASO 1: RETRIEVAL
        palabras = pregunta.split()
        q_obj = Q()
        for p in palabras:
            if len(p) > 3:
                q_obj |= Q(texto_detectado__icontains=p) | Q(tags_ia__icontains=p)
        
        docs_contexto = Documento.objects.filter(q_obj, usuario=request.user).order_by('-id')[:3]
        
        texto_contexto = ""
        for d in docs_contexto:
            texto_contexto += f"\n- DOC '{d.titulo}': {d.texto_detectado[:800]}..."

        # PASO 2: GENERACIÓN
        if USA_BEDROCK and bedrock_client:
            try:
                prompt = f"""Eres un asistente de Retail. Responde usando SOLO este contexto:
                {texto_contexto}
                
                Pregunta: {pregunta}
                """

                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                })

                response = bedrock_client.invoke_model(
                    body=body, 
                    modelId="anthropic.claude-3-haiku-20240307-v1:0",
                    accept='application/json', contentType='application/json'
                )
                
                resp_body = json.loads(response.get('body').read())
                response_data['texto'] = resp_body['content'][0]['text']
                response_data['acciones'] = [{'label': 'Ver Fuentes', 'action': 'show_sources'}]

            except Exception as e:
                print(f"Error Bedrock: {e}")
                response_data['texto'] = "Error conectando con el cerebro IA."

        else:
            # MODO SIMULACIÓN
            time.sleep(1)
            
            if 'factura' in pregunta or 'vence' in pregunta:
                response_data['texto'] = (
                    "⚠️ **(Simulación)** Alerta de Tesorería Detectada.\n"
                    "El sistema RAG encontró una factura próxima a vencer en tus documentos."
                )
                if docs_contexto:
                    response_data['texto'] += f"\nFuente: {docs_contexto[0].titulo}"
                
                response_data['acciones'] = [
                    {'label': '📧 Notificar Contabilidad', 'action': 'notify'},
                    {'label': '💰 Bloquear SAP', 'action': 'block'}
                ]
            
            elif 'rot' in pregunta or 'calidad' in pregunta:
                response_data['texto'] = "🔍 **(Simulación)** Reporte de Calidad: Se detectaron productos dañados en las imágenes analizadas."
                response_data['acciones'] = [{'label': 'Generar Reclamo', 'action': 'claim'}]
            
            else:
                response_data['texto'] = "Modo Laboratorio: No tengo acceso a Bedrock aún, pero busqué en tu base de datos."
                if docs_contexto:
                    response_data['texto'] += f"\nEncontré estos documentos relacionados: {[d.titulo for d in docs_contexto]}"
                else:
                    response_data['texto'] += "\nNo encontré documentos que coincidan con tu búsqueda."

        return JsonResponse(response_data)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def visualizar_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)
    # Seguridad básica
    if doc.usuario != request.user:
         return redirect('subir_archivo')

    es_imagen = doc.archivo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))
    return render(request, 'gestion/visualizar.html', {'doc': doc, 'es_imagen': es_imagen})

def descargar_documento(request, documento_id):
    doc = get_object_or_404(Documento, id=documento_id)
    if doc.usuario != request.user:
         return redirect('subir_archivo')
         
    client = boto3.client('s3', 
                          aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                          region_name='us-east-1')
    try:
        url_descarga = client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': doc.archivo.name,
                'ResponseContentDisposition': f'attachment; filename="{doc.archivo.name.split("/")[-1]}"'
            },
            ExpiresIn=3600
        )
        return redirect(url_descarga)
    except Exception as e:
        print(f"Error descarga: {e}")
        return redirect(doc.archivo.url)
