from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField

class Documento(models.Model):
   titulo = models.CharField(max_length=200, blank=True, null=True)
   #Este campo enviara los archivos al s3
   archivo = models.FileField(upload_to='documentos_perfumeria/')
   fecha = models.DateTimeField(auto_now_add=True)
   usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    # este campo vincula el archivo con el usuario conectado

   
    # ESTADO: Vamos a estandarizar los estados para que Celery los use
   OPCIONES_ESTADO = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando IA'),
        ('completado', 'Completado'),
        ('error', 'Error'),

        
   ] 
   estado = models.CharField(max_length=20, choices=OPCIONES_ESTADO, default='pendiente')


   # --- CAMPOS PARA IA ---
   # guardamos etiquetas (ej. ["perfume", "vidrio", "rojo"])  
   # usamos JSONField porque postgres es expeerto manejando esto

   tags_ia = models.JSONField(null=True, blank=True)


   # guardamos texto detectado (OCR)o descripciones
   texto_detectado = models.TextField(null=True, blank=True)

   # porcentaje de confianza (ej: 0.98 o 98% )
   confianza_ia = models.FloatField(null= True, blank=True)

   



   def __str__(self):
      return self.titulo
