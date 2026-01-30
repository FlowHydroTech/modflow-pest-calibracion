# Definir variable PROJECT_NAME con el nombre del modelo a calibrar
#mostrar IP del servidor Master
echo "Tu(s) IP(s): $(hostname -I)"

echo "----------------------------------------"
echo "Este script se llama: $0"
echo "BUCKET_NAME: $BUCKET_NAME"
echo "EJECUTABLE_AUTONOMO: $EJECUTABLE_AUTONOMO"
echo "NOMBRE_MODELO_PEST: $NOMBRE_MODELO_PEST"
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Comando a ejecutar: cd /app/modelo/"

cd /app/modelo/

echo "----------------------------------------"
echo "----------------------------------------"
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
#comando wine para ejecutar PEST
CMD="wine $EJECUTABLE_AUTONOMO $NOMBRE_MODELO_PEST"
echo "Comando a ejecutar: $CMD"
START=$(date +%s)
$CMD
END=$(date +%s)

DIFF=$((END - START))
echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
echo "El comando tardó $DIFF segundos en ejecutarse."
echo "----------------------------------------"

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
