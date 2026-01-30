# crear repositorio master oregon
aws ecr create-repository --repository-name pest-talabre-master --region us-west-2
# Autenticarse en ECR oregon
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-west-2.amazonaws.com
# Etiquetar la imagen oregon
docker tag pest-talabre-master:latest 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-talabre-master:latest
# Subir la imagen oregon
docker push 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-talabre-master:latest

# crear repositorio agente oregon
aws ecr create-repository --repository-name pest_talabre_agente --region us-west-2
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-west-2.amazonaws.com
docker tag pest-talabre-agente:latest 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-talabre-agente:latest
docker push 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-talabre-agente:latest


# crear repositorio agente Virginia
aws ecr create-repository --repository-name pest-talabre-agente --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-east-1.amazonaws.com
docker tag pest-talabre-agente:latest 312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-agente:latest
docker push 312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-agente:latest

# crear repositorio agente Ohio
aws ecr create-repository --repository-name pest-talabre-agente --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-east-2.amazonaws.com
docker tag pest-talabre-agente:latest 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-talabre-agente:latest
docker push 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-talabre-agente:latest

# crear repositorio pest-mod-res-ensi master Ohio
aws ecr create-repository --repository-name pest-mod-res-ensi-master --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-east-2.amazonaws.com
docker tag pest-mod-res-ensi-master:latest 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi-master:latest
docker push 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi-master:latest

# crear repositorio pest-mod-res-ensi agente Ohio
aws ecr create-repository --repository-name pest-mod-res-ensi --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-east-2.amazonaws.com
docker tag pest-mod-res-ensi:latest 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi:latest
docker push 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi:latest


aws ecr create-repository --repository-name pest-mod-res-ensi --region us-west-2
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-west-2.amazonaws.com
docker tag pest-mod-res-ensi:latest 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-mod-res-ensi:latest
docker push 312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-mod-res-ensi:latest

aws ecr create-repository --repository-name pest-mod-res-ensi --region us-east-2
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 312019940349.dkr.ecr.us-east-2.amazonaws.com
docker tag pest-mod-res-ensi:latest 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi:latest
docker push 312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi:latest