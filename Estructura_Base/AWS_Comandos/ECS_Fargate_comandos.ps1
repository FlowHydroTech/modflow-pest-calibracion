#1. Listar las tareas en ejecución:
aws ecs list-tasks --cluster mod-res-ensi-cluster-us-west-2 --region us-west-2
#2. Obtener el ARN completo de la tarea:
aws ecs describe-tasks --cluster mod-res-ensi-cluster-us-west-2 --tasks arn:aws:ecs:us-west-2:312019940349:task/mod-res-ensi-cluster-us-west-2/2acb47af6686429d9e1ab83c65bf2779 --region us-west-2
3. Conectarte con ECS Exec:
aws ecs execute-command --cluster mod-res-ensi-cluster-us-west-2 --task arn:aws:ecs:us-west-2:312019940349:task/mod-res-ensi-cluster-us-west-2/2acb47af6686429d9e1ab83c65bf2779 --container mod-res-ensi-master-container --interactive --command "/bin/bash" --region us-west-2

comando combinado:
$taskArn = (aws ecs list-tasks --cluster mod-res-ensi-cluster-us-west-2 --service-name mod-res-ensi-master-service --region us-west-2 --query 'taskArns[0]' --output text)
aws ecs execute-command --cluster mod-res-ensi-cluster-us-west-2 --task $taskArn --container mod-res-ensi-master-container --interactive --command "/bin/bash" --region us-west-2

arn:aws:ecs:us-west-2:312019940349:task/mod-res-ensi-cluster-us-west-2/2acb47af6686429d9e1ab83c65bf2779