# Definir variable PROJECT_NAME con el nombre del modelo a calibrar
#mostrar IP del servidor Master
echo "Tu(s) IP(s): $(hostname -I)"
echo "----------------------------------------"
echo "Este script se llama: $0"
echo "BUCKET_NAME: $BUCKET_NAME"
echo "EJECUTABLE_MASTER: $EJECUTABLE_MASTER"
echo "NOMBRE_MODELO_PEST: $NOMBRE_MODELO_PEST"
echo "COMANDO_MASTER: $COMANDO_MASTER"
echo "PEST_PORT: $PEST_PORT"
echo "----------------------------------------"
echo "----------------------------------------"
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
cd /app/modelo/

# Verificar que el ejecutable existe
if [ ! -f "$EJECUTABLE_MASTER" ]; then
    echo "ERROR: Ejecutable no encontrado: $EJECUTABLE_MASTER"
    echo "Archivos disponibles:"
    ls -la
    exit 1
fi

# Definir el comando en una variable
CMD="wine $EJECUTABLE_MASTER $NOMBRE_MODELO_PEST $COMANDO_MASTER :$PEST_PORT"

# Mostrar fecha y comando
echo "Fecha de inicio de modelo: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Comando a ejecutar: $CMD"
echo "----------------------------------------"

# Guardar tiempo inicial
START=$(date +%s)

# Ejecutar el comando con manejo de errores
if $CMD; then
    # Guardar tiempo final
    END=$(date +%s)
    DIFF=$((END - START))
    echo "----------------------------------------"
    echo "El comando completó exitosamente en $DIFF segundos."
    echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
else
    EXIT_CODE=$?
    END=$(date +%s)
    DIFF=$((END - START))
    echo "----------------------------------------"
    echo "ERROR: El comando falló con código $EXIT_CODE después de $DIFF segundos."
    echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
fi

echo "----------------------------------------"
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Comando a ejecutar: aws s3 cp /app/modelo s3://$BUCKET_NAME/modelo --recursive"
START=$(date +%s)
aws s3 cp /app/modelo s3://$BUCKET_NAME/modelo --recursive
END=$(date +%s)
DIFF=$((END - START))
echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
echo "El comando tardó $DIFF segundos en ejecutarse."
echo "----------------------------------------"
echo "Proceso finalizado."
