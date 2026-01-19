#talabre autonomo
python getLog.py --log-group "/ecs/agente_talabre" --region us-west-2 --start 2025-12-01 --end 2025-12-12 --output talabre_autonomo_logs20251211_1746.xlsx --format excel
#talabre master - agentes
python getLog.py --log-group "pest-talabre-ec2-central" --region us-west-2 --start 2025-12-01 --end 2025-12-12 --output talabre_master_logs20251211_2327.xlsx --format excel
python getLog.py --log-group "pest-talabre-ec2-central-container" --region us-west-2 --start 2025-12-01 --end 2025-12-12 --output talabre_master_contenedor_logs20251211_2327.xlsx --format excel
python getLog.py --log-group "/ecs/pest-talabre/hosts" --region us-west-2 --start 2025-12-10 --end 2025-12-12 --output talabre_agente_logs20251211_2327.xlsx --format excel
#mod-res-ensi
python getLog.py --log-group "/ecs/mod-res-ensi-us-west-2-master" --region us-west-2 --start 2026-01-01 --end 2026-01-15 --output mod_res_ensi_master_logs20260113_2252.xlsx --format excel
python getLog.py --log-group "/ecs/mod-res-ensi-us-west-2-agente" --region us-west-2 --start 2026-01-01 --end 2026-01-15 --output mod_res_ensi_agente_logs20260113_2252.xlsx --format excel
#mod-res-ensi
python getLog.py --log-group "/ecs/mod-res-ensi-us-east-2-master" --region us-east-2 --start 2025-12-01 --end 2025-12-30 --output mod_res_ensi_master_logs20251219_1348.xlsx --format excel
python getLog.py --log-group "/ecs/mod-res-ensi-us-east-2-agente" --region us-east-2 --start 2025-12-01 --end 2025-12-30 --output mod_res_ensi_agente_logs20251219_1348.xlsx --format excel
#talabre v2
python getLog.py --log-group "/ecs/pest-talabre-v2-us-east-1-agente" --region us-east-1 --start 2025-12-01 --end 2025-12-30 --output talabre_agente_logs20251219_1346.xlsx --format excel
python getLog.py --log-group "/ecs/pest-talabre-v2-us-east-1-master" --region us-east-1 --start 2025-12-01 --end 2025-12-30 --output talabre_master_logs20251219_1346.xlsx --format excel

