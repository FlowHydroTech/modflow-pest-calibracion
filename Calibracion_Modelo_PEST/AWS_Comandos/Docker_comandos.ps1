# Construir la imagen Docker usando el Dockerfile en el directorio actual
docker build -t pest-test .



#mostrar el historial de la imagen docker
docker history --no-trunc pest-mod-res-ensi

# Limpiar imágenes intermedias no utilizadas para liberar espacio
docker builder prune -f

# Limpiar todas las imágenes Docker no utilizadas para liberar espacio
docker image prune -a