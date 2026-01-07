"""
URL configuration for retail_dam project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from gestion import views

# importamos la vista de la app gestion
from gestion.views import subir_archivo_view, eliminar_documento

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esto activa las vista de login y logout de django automaticamente
    path('accounts/', include('django.contrib.auth.urls')),
  # ruta principal: si entran a la raiz, van a subir archivos
    path('', subir_archivo_view, name='subir_archivo'),
    path('eliminar/<int:documento_id>/', views.eliminar_documento, name='eliminar_documento'),

    path('buscar/', views.lista_documentos, name='lista_documentos'),
    
]

# Configuración para que se vean las imágenes en modo desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
