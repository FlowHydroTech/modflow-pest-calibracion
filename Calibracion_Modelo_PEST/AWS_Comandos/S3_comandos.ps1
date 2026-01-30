# respaldo de carpeta app/modelo del master en s3 mod-res-ensi
aws s3 cp /app/modelo s3://312019940349-pest-mod-res-ensi-west-2/modelo --recursive
aws s3 cp /app/modelo s3://312019940349-pest-mod-res-ensi-west-2/backup/20251216_1652 --recursive #backup adicional
# respaldo de carpeta app/modelo del master en s3 talabre
aws s3 cp /app/modelo s3://312019940349-pest-talabre/modelo --recursive

#respaldar bucket localmente
aws s3 sync s3://312019940349-pest-talabre/modelo . --region us-west-2
aws s3 sync s3://312019940349-pest-mod-res-ensi/modelo . --region us-east-1

aws s3 sync s3://312019940349-pest-mod-res-ensi-west-2/modelo . --region us-west-2