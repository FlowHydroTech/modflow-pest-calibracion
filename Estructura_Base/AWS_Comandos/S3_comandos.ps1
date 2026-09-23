# respaldo de carpeta app/modelo del master en s3 mod-res-ensi
aws s3 cp /app/modelo s3://312019940349-pest-mod-res-ensi-west-2/modelo --recursive
aws s3 cp /app/modelo s3://312019940349-pest-mod-res-ensi-west-2/backup/20251216_1652 --recursive #backup adicional
# respaldo de carpeta app/modelo del master en s3 talabre
aws s3 cp /app/modelo s3://312019940349-pest-talabre/modelo --recursive

#respaldar bucket localmente
aws s3 sync s3://312019940349-pest-talabre/modelo . --region us-west-2
aws s3 sync s3://312019940349-pest-mod-res-ensi/modelo . --region us-east-1

aws s3 sync s3://312019940349-pest-mod-res-ensi-west-2/modelo . --region us-west-2
aws s3 sync s3://312019940349-pest-cmdic-linux-ensi-west-2/modelo-20260809_2020 . --region us-west-2
aws s3 sync s3://312019940349-pest-cmdic-linux-ensi-west-2/modelo . --region us-west-2


aws s3 cp /app/modelo s3://312019940349-pest-cmdic-linux-ensi-west-2/modelo_master_20260826_1804 --recursive
aws s3 sync s3://312019940349-pest-cmdic-linux-ensi-west-2/modelo_master_20260826_1804 . --region us-west-2


aws s3 sync s3://312019940349-pest-talabre-east-1/modelo . --region us-east-1


# respaldo de archivos de log del master
aws s3 cp /app/modelo/cmdic_rajos_ensi.rec s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rec
aws s3 cp /app/modelo/cmdic_rajos_ensi.rei s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rei
aws s3 cp /app/modelo/cmdic_rajos_ensi.rls s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rls
aws s3 cp /app/modelo/cmdic_rajos_ensi.rme s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rme
aws s3 cp /app/modelo/cmdic_rajos_ensi.rmr s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rmr
aws s3 cp /app/modelo/cmdic_rajos_ensi.rst s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.rst
aws s3 cp /app/modelo/cmdic_rajos_ensi.sen  s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510/cmdic_rajos_ensi.sen 

aws s3 sync s3://312019940349-pest-cmdic-linux-ensi-west-2/master_rec_20260909_1510 . --region us-west-2