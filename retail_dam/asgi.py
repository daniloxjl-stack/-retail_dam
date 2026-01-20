"""
ASGI config for retail_dam project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import gestion.routing  # Importamos las rutas que creamos en el paso 4

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retail_dam.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            gestion.routing.websocket_urlpatterns
        )
    ),
})
