$TASK_ID = aws ecs list-tasks `
    --cluster mod-res-ensi-cluster-us-east-2 `
    --service-name mod-res-ensi-master-service `
    --region us-east-2 `
    --query 'taskArns[0]' `
    --output text | ForEach-Object { $_.Split('/')[-1] }

echo "El TASK_ID del MASTER es: $TASK_ID"

aws ecs execute-command `
  --cluster mod-res-ensi-cluster-us-east-2 `
  --task $TASK_ID `
  --container mod-res-ensi-master `
  --interactive `
  --command "/bin/bash" `
  --region us-east-2

#una vez dentro del contenedor, ejecutar el siguiente comando para respaldar la carpeta /app/modelo en el bucket s3
aws s3 cp /app/modelo s3://312019940349-pest-mod-res-ensi-east-2/backup/20260131_1900 --recursive

#para salir de la sesion del contenedor y volver al host local
exit

#Crear una carpeta para el respaldo localmente
mkdir respaldo_mod-res-ensi_east2_20260131_1900

#ingresar a la carpeta creada
cd respaldo_mod-res-ensi_east2_20260131_1900
#descargar datos del bucket a la maquina local (.) significa la carpeta actual donde está la consola.
aws s3 sync s3://312019940349-pest-mod-res-ensi-east-2/backup/20260131_1900 . --region us-east-2
