#!/bin/bash
echo "Tu(s) IP(s): $(hostname -I)"
echo "----------------------------------------"
echo "Este script se llama: $0"
echo "Tu(s) IP(s): $(hostname -I)"
echo "MASTER_HOST: $MASTER_HOST"
echo "NOMBRE_MODELO_PEST: $NOMBRE_MODELO_PEST"
echo "PEST_PORT: $PEST_PORT"
echo "EJECUTABLE_AGENTE: $EJECUTABLE_AGENTE"
#test de conectividad a servidor Master
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Realizando ping a $MASTER_HOST..."
ping -c 4 $MASTER_HOST
echo "Fecha de término: $(date '+%Y-%m-%d %H:%M:%S')"

# ingresar a carpeta del modelo
echo "ejecutando cd /app/modelo/"
cd /app/modelo/
# Definir el comando en una variable
CMD="wine $EJECUTABLE_AGENTE $NOMBRE_MODELO_PEST /h $MASTER_HOST:$PEST_PORT"
# Mostrar fecha y comando
echo "Fecha de inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Comando a ejecutar: $CMD"

# Guardar tiempo inicial
START=$(date +%s)

# Ejecutar el comando
$CMD

# Guardar tiempo final
END=$(date +%s)
DIFF=$((END - START))

# Mostrar resultado
echo "El comando tardó $DIFF segundos en ejecutarse."