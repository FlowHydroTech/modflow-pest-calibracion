#!/bin/bash
set -e

echo "Tu(s) IP(s): $(hostname -I)"
echo "----------------------------------------"
echo "Este script se llama: $0"
echo "MASTER_HOST: $MASTER_HOST"
echo "NOMBRE_MODELO_PEST: $NOMBRE_MODELO_PEST"
echo "PEST_PORT: $PEST_PORT"
echo "EJECUTABLE_AGENTE: $EJECUTABLE_AGENTE"
echo "COMANDO_AGENTE: $COMANDO_AGENTE"
echo "BUCKET_NAME: $BUCKET_NAME"
echo "WINE_CPU_TOPOLOGY: ${WINE_CPU_TOPOLOGY:-not set}"
echo "WINEARCH: ${WINEARCH:-not set}"
echo "WINEPREFIX: ${WINEPREFIX:-not set}"
echo "----------------------------------------"

# Configurar variables de Wine si no están definidas
export WINEARCH=${WINEARCH:-win64}
export WINEPREFIX=${WINEPREFIX:-/root/.wine}
export DISPLAY=${DISPLAY:-:0}

# Verificar que Wine esté disponible
echo "Verificando Wine..."
if ! command -v wine &> /dev/null; then
    echo "ERROR CRÍTICO: Wine no está instalado en el contenedor"
    exit 1
fi
echo "Wine version: $(wine --version)"

# Verificar que WINEPREFIX existe y está inicializado
echo "Verificando WINEPREFIX en $WINEPREFIX..."
if [ ! -d "$WINEPREFIX" ]; then
    echo "ERROR: WINEPREFIX no existe. Debe ser inicializado en el Dockerfile"
    exit 1
fi

# Verificar que system.reg existe (signo de que Wine está inicializado)
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "ADVERTENCIA: Wine podría no estar completamente inicializado. Reintentando..."
    # Usar lock file para evitar race conditions
    LOCK_FILE="/tmp/wine_init.lock"
    exec 200>"$LOCK_FILE"
    
    # Intentar obtener el lock (esperar máximo 30 segundos)
    if flock -w 30 200; then
        echo "Lock adquirido. Inicializando Wine..."
        wineboot -i 2>&1 || true
        sleep 1
        wineboot -e 2>&1 || true
    else
        echo "ERROR: No se pudo adquirir lock para inicialización de Wine"
        exit 1
    fi
else
    echo "WINEPREFIX ya está inicializado correctamente"
fi

# Test de conectividad a servidor Master
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Realizando ping a $MASTER_HOST..."
if ping -c 4 $MASTER_HOST 2>/dev/null; then
    echo "Conectividad con Master establecida"
else
    echo "ADVERTENCIA: No se pudo conectar con ping a $MASTER_HOST"
fi
echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"

# Ingresar a carpeta del modelo
echo "Cambiando a directorio /app/modelo/"
cd /app/modelo/

# Verificar que el ejecutable existe
if [ ! -f "$EJECUTABLE_AGENTE" ]; then
    echo "ERROR: Ejecutable no encontrado: $EJECUTABLE_AGENTE"
    echo "Archivos disponibles:"
    ls -la
    exit 1
fi

# Definir el comando en una variable
CMD="wine $EJECUTABLE_AGENTE $NOMBRE_MODELO_PEST $COMANDO_AGENTE $MASTER_HOST:$PEST_PORT"

# Mostrar fecha y comando
echo "Fecha de inicio de modelo: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Comando a ejecutar: $CMD"
echo "----------------------------------------"

# Guardar tiempo inicial
START=$(date +%s)

# Ejecutar el comando con reintentos en caso de error de memoria compartida
MAX_RETRIES=2
RETRY_COUNT=0

while [ $RETRY_COUNT -le $MAX_RETRIES ]; do
    if $CMD; then
        # Guardar tiempo final
        END=$(date +%s)
        DIFF=$((END - START))
        echo "----------------------------------------"
        echo "El comando completó exitosamente en $DIFF segundos."
        echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
        #exit 0
    else
        EXIT_CODE=$?
        RETRY_COUNT=$((RETRY_COUNT + 1))
        
        if [ $RETRY_CODE -eq 80 ] || echo "wine: failed to map the shared user data" 2>&1 | grep -q "c0000018"; then
            if [ $RETRY_COUNT -le $MAX_RETRIES ]; then
                echo "ADVERTENCIA: Error c0000018 detectado. Reintentando ($RETRY_COUNT/$MAX_RETRIES)..."
                sleep 5
                continue
            fi
        fi
        
        END=$(date +%s)
        DIFF=$((END - START))
        echo "----------------------------------------"
        echo "ERROR: El comando falló con código $EXIT_CODE después de $DIFF segundos."
        echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
        #exit $EXIT_CODE
    fi
done

exit 1