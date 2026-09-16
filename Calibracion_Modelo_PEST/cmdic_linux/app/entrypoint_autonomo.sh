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
CMD="$EJECUTABLE_AUTONOMO $NOMBRE_MODELO_PEST"
echo "Comando a ejecutar: $CMD"
START=$(date +%s)
$CMD
END=$(date +%s)

DIFF=$((END - START))
echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"
echo "El comando tardó $DIFF segundos en ejecutarse."
echo "--- Recursos tras ejecución ---"
echo "CPU (load avg):  $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
echo "RAM:             $(free -h | awk '/^Mem:/ {print "total="$2, "usado="$3, "libre="$4}')"
echo "Disco:           $(df -h /app | awk 'NR==2 {print "total="$2, "usado="$3, "libre="$4, "uso="$5}')"
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
