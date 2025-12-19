#Mirar instancias activas en la región us-west-2
aws ssm describe-instance-information --region us-west-2

#Conectar a la consola SSM de una instancia específica
aws ssm start-session --region us-west-2 --target i-0ae7ca009a6b55a0b
#Reemplazar "i-0ae7ca009a6b55a0b" con el ID de la instancia deseada



