import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Obtener el ID del usuario logueado
        self.user_id = self.scope["user"].id
        self.group_name = f"user_{self.user_id}"

        # 2. Unir al usuario a su grupo privado (Ej: "user_1")
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Salir del grupo al desconectar
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # ... (Mantén tu lógica actual del chat aquí) ...
        # (El código del chat que ya tenías para el streaming)
        text_data_json = json.loads(text_data)
        mensaje = text_data_json['message']
        
        # Simulación de respuesta IA (Streaming)
        await self.send(text_data=json.dumps({'type': 'start'}))
        for palabra in f"Analizando solicitud: {mensaje}...".split():
            await asyncio.sleep(0.05)
            await self.send(text_data=json.dumps({'type': 'chunk', 'message': palabra + " "}))
        await self.send(text_data=json.dumps({'type': 'end'}))

    # --- NUEVO MÉTODO PARA RECIBIR SEÑALES DE CELERY ---
    async def doc_status(self, event):
        # Este método se activa cuando Celery manda un mensaje tipo "doc.status"
        datos = event['data']
        
        # Reenviamos el mensaje al Javascript
        await self.send(text_data=json.dumps({
            'type': 'doc_update',  # Tipo de mensaje para el JS
            'doc_id': datos['doc_id'],
            'status': 'listo',
            'tags': datos['tags'],
            'texto': datos['texto_preview']
        }))
