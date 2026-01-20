from celery import shared_task
from django.conf import settings
from .models import Documento
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import boto3
import time
import random
import zipfile
import xml.etree.ElementTree as ET
import io

# --- CONFIGURACIÓN ---
MODO_LABORATORIO_BEDROCK = True 

@shared_task
def procesar_archivo_ia(documento_id):
    print(f"--- [CELERY] Iniciando tarea para Documento ID: {documento_id} ---")
    
    try:
        # 1. Buscar documento
        doc = Documento.objects.get(id=documento_id)
        doc.estado = 'procesando'
        doc.save()

        # 2. Configurar S3
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        file_name = doc.archivo.name
        # Truco: sacamos la extensión en minúsculas
        ext = file_name.split('.')[-1].lower()

        # Clientes AWS
        client_s3 = boto3.client('s3', region_name='us-east-1')
        client_rek = boto3.client('rekognition', region_name='us-east-1')
        client_textract = boto3.client('textract', region_name='us-east-1')
        
        tags_finales = []
        texto_final = ""
        embedding_final = None 

        # ==============================================================================
        # PASO A: EXTRACCIÓN DE TEXTO (LÓGICA MULTI-FORMATO)
        # ==============================================================================
        print(f"--> [IA] Iniciando extracción para formato: {ext}")
        
        try:
            # --- CASO 1: TEXTO PLANO (.txt) ---
            if ext == 'txt':
                # Descargamos directo a memoria y leemos
                obj = client_s3.get_object(Bucket=bucket_name, Key=file_name)
                texto_final = obj['Body'].read().decode('utf-8')
                print(f"--> [IA] TXT leído exitosamente.")

            # --- CASO 2: WORD (.docx) ---
            elif ext == 'docx':
                # El .docx es en realidad un ZIP con XMLs adentro. Lo abrimos nativamente.
                obj = client_s3.get_object(Bucket=bucket_name, Key=file_name)
                buffer = io.BytesIO(obj['Body'].read())
                
                with zipfile.ZipFile(buffer) as z:
                    xml_content = z.read('word/document.xml')
                    tree = ET.fromstring(xml_content)
                    
                    # Namespace oficial de Word
                    namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    textos = []
                    # Buscamos todas las etiquetas de texto <w:t>
                    for node in tree.iterfind('.//w:t', namespaces):
                        if node.text:
                            textos.append(node.text)
                    texto_final = "\n".join(textos)
                print(f"--> [IA] DOCX procesado exitosamente.")

            # --- CASO 3: IMÁGENES (JPG, PNG) -> TEXTRACT SÍNCRONO ---
            elif ext in ['jpg', 'jpeg', 'png', 'tiff', 'tif']:
                response = client_textract.detect_document_text(
                    Document={'S3Object': {'Bucket': bucket_name, 'Name': file_name}}
                )
                lineas = [item['Text'] for item in response['Blocks'] if item['BlockType'] == 'LINE']
                texto_final = "\n".join(lineas)

            # --- CASO 4: PDF -> TEXTRACT ASÍNCRONO ---
            elif ext == 'pdf':
                start = client_textract.start_document_text_detection(
                    DocumentLocation={'S3Object': {'Bucket': bucket_name, 'Name': file_name}}
                )
                job_id = start['JobId']
                print(f"--> [IA] Job PDF iniciado: {job_id}")

                while True:
                    status = client_textract.get_document_text_detection(JobId=job_id)
                    if status['JobStatus'] in ['SUCCEEDED', 'FAILED']:
                        if status['JobStatus'] == 'SUCCEEDED':
                            lineas = [item['Text'] for item in status['Blocks'] if item['BlockType'] == 'LINE']
                            texto_final = "\n".join(lineas)
                        break
                    time.sleep(2)

            else:
                texto_final = "Formato no soportado para extracción automática."

        except Exception as e:
            print(f"Error extrayendo texto: {e}")
            texto_final = f"Error de lectura: {str(e)}"

        # ==============================================================================
        # PASO B: ANÁLISIS VISUAL (Solo Imágenes)
        # ==============================================================================
        if ext in ['jpg', 'jpeg', 'png']:
            try:
                rek = client_rek.detect_labels(
                    Image={'S3Object': {'Bucket': bucket_name, 'Name': file_name}},
                    MaxLabels=5,
                    MinConfidence=90
                )
                tags_finales = [l['Name'] for l in rek['Labels']]
            except Exception as e:
                print(f"Error Rekognition: {e}")

        # ==============================================================================
        # PASO C: GUARDAR
        # ==============================================================================
        
        # Generar vector simulado para la demo
        if MODO_LABORATORIO_BEDROCK:
            embedding_final = [random.uniform(-1.0, 1.0) for _ in range(1536)]

        doc.tags_ia = tags_finales
        doc.texto_detectado = texto_final
        doc.embedding = embedding_final
        doc.estado = 'completado'
        doc.save()

        print(f"--- [CELERY] Tarea FINALIZADA OK ---")
        return "OK"

    except Exception as e:
        print(f"ERROR CRITICO: {e}")
        return "Error"

    # --- NOTIFICACIÓN WEBSOCKET (NUEVO) ---
        channel_layer = get_channel_layer()
        
        # Enviamos el mensaje al grupo del usuario dueño del documento
        async_to_sync(channel_layer.group_send)(
            f"user_{doc.usuario.id}",  # Nombre del grupo (mismo que en consumers.py)
            {
                "type": "doc.status",  # Esto busca el método 'doc_status' en el consumer
                "data": {
                    "doc_id": doc.id,
                    "tags": doc.tags_ia,
                    "texto_preview": doc.texto_detectado[:100] if doc.texto_detectado else "..."
                }
            }
        )
        return f"Documento {doc_id} procesado y notificado."
