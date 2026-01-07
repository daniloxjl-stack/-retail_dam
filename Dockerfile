# Usamos una imagen oficial de Python ligera
FROM python:3.9-slim

# Evita que Python guarde archivos .pyc y fuerza los logs a la consola
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema (para que funcionen ciertas librerías)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar y instalar requerimientos
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copiar todo el código del proyecto al contenedor
COPY . /app/
