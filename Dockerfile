# Usa una imagen base de Python slim
FROM python:3.12-slim

# Establece el directorio de trabajo en el contenedor
WORKDIR /app

# Copia primero el archivo de requerimientos para aprovechar el caché de Docker
COPY requirements.txt .

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia todos los módulos Python del directorio raíz para evitar omitir
# nuevas dependencias top-level en futuros releases.
COPY *.py ./

# Copia las carpetas de templates y static
# Asegúrate de que tu logo.png está DENTRO de la carpeta 'static' en tu máquina local antes de construir
COPY templates/ ./templates/
COPY static/ ./static/

# Expón el puerto en el que corre la aplicación (buenas prácticas)
EXPOSE 5000

# Define el comando para ejecutar la aplicación usando el script principal correcto (app.py)
# Usa python -u para forzar salida no almacenada en búfer para stdout/stderr
CMD ["python", "-u", "app.py"]
