import os
from celery import Celery

# Establecer el módulo de configuración de Django por defecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retail_dam.settings')

app = Celery('retail_dam')

# Usar una cadena aquí significa que el trabajador no tiene que serializar
# el objeto de configuración a los procesos hijos.
# - namespace='CELERY' significa que todas las claves de conf. relacionadas con celery
#   deben tener el prefijo 'CELERY_'.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Cargar tareas de todos los módulos de aplicaciones de Django registrados.
app.autodiscover_tasks()
