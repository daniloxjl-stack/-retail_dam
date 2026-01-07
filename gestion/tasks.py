from celery import shared_task
from django.conf import settings
from .models import Documento
import boto3
import os

@shared_task
def procesar_imagen_ia(documento_id):
    try:
        print(f"--- INICIO TAREA IA para documento ID: {documento_id} ---")
        
        # 1. Buscar el archivo en la DB
        doc = Documento.objects.get(id=documento_id)
        
        # Actualizamos estado
        doc.estado = 'procesando'
        doc.save()

        # Obtenemos datos de S3
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        file_name = doc.archivo.name
        
        # DEBUG: Imprimir esto es vital para ver qué está pasando
        print(f"--- DEBUG S3: Bucket='{bucket_name}' | Key='{file_name}' ---")

        # Inicializamos clientes
        client_rek = boto3.client('rekognition', region_name='us-east-1')
        client_text = boto3.client('textract', region_name='us-east-1')
        
        # ### NUEVO 1: Cliente de Translate ###
        client_trans = boto3.client('translate', region_name='us-east-1')

        mis_tags = []
        texto_final = ""
        errores = []

        # --- PARTE 1: AWS REKOGNITION (Solo JPG/PNG) ---
        # Validamos extensión
        ext = os.path.splitext(file_name)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png']:
            try:
                print("--- Intentando Rekognition (Etiquetas)...")
                response_rek = client_rek.detect_labels(
                    Image={'S3Object': {'Bucket': bucket_name, 'Name': file_name}},
                    MaxLabels=10,
                    MinConfidence=75
                )
                
                # ### NUEVO 2: Lógica de Traducción (Reemplaza la lista simple anterior) ###
                tags_detectados = response_rek['Labels']
                print(f"--- Rekognition encontró {len(tags_detectados)} etiquetas en inglés. Traduciendo...")

                for label in tags_detectados:
                    nombre_ingles = label['Name']
                    try:
                        # Llamamos a Amazon Translate
                        resp_traduccion = client_trans.translate_text(
                            Text=nombre_ingles,
                            SourceLanguageCode='en',
                            TargetLanguageCode='es'
                        )
                        mis_tags.append(resp_traduccion['TranslatedText'])
                    except Exception as e_trans:
                        # Si falla la traducción, guardamos el original en inglés para no perder el dato
                        print(f"Error traduciendo '{nombre_ingles}': {e_trans}")
                        mis_tags.append(nombre_ingles)
                
                print(f"--- Traducción finalizada: {mis_tags} ---")
                # ### FIN NUEVO ###

            except Exception as e_rek:
                error_msg = f"Error Rekognition: {str(e_rek)}"
                print(error_msg)
                errores.append(error_msg)
        else:
            print(f"--- Saltando Rekognition: El formato {ext} no es compatible (Solo JPG/PNG) ---")

        # --- PARTE 2: AWS TEXTRACT (OCR - Texto) ---
        try:
            print("--- Intentando Textract (OCR)...")
            response_text = client_text.detect_document_text(
                Document={'S3Object': {'Bucket': bucket_name, 'Name': file_name}}
            )
            
            lineas_texto = []
            for item in response_text['Blocks']:
                if item['BlockType'] == 'LINE':
                    lineas_texto.append(item['Text'])
            
            texto_final = "\n".join(lineas_texto)
            print(f"--- Textract Éxito: {len(lineas_texto)} líneas leídas ---")

        except Exception as e_text:
            error_msg = f"Error Textract: {str(e_text)}"
            print(error_msg)
            errores.append(error_msg)


        # --- GUARDADO FINAL ---
        doc.tags_ia = mis_tags
        doc.texto_detectado = texto_final
        
        if errores:
            # Si hubo errores parciales, guardamos el log pero marcamos completado si algo funcionó
            doc.estado = 'completado_con_alertas' if (mis_tags or texto_final) else 'error'
            print(f"--- Errores detectados: {errores}")
        else:
            doc.estado = 'completado'
            
        doc.save()

        return f"Proceso finalizado. Tags: {len(mis_tags)} | Texto: {len(texto_final)} chars"

    except Documento.DoesNotExist:
        return f"Error: Documento {documento_id} no encontrado."
    
    except Exception as e:
        print(f"ERROR CRITICO GENERAL: {e}")
        try:
            doc.estado = 'error'
            doc.save()
        except:
            pass
        return f"Error critico: {e}"
