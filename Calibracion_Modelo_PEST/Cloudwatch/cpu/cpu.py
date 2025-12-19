import boto3
import csv
from datetime import datetime, timedelta

# Configuración
region = "us-east-2"              # Cambia a tu región
cluster_name = "pest-mod-res-ensi-ecs-east2"       # Nombre de tu cluster ECS
hours_back = 1                    # Rango de tiempo en horas hacia atrás

ecs = boto3.client("ecs", region_name=region)
cloudwatch = boto3.client("cloudwatch", region_name=region)

# Obtener lista de servicios en el cluster
services_arns = ecs.list_services(cluster=cluster_name)["serviceArns"]
services = ecs.describe_services(cluster=cluster_name, services=services_arns)["services"]

# Rango de tiempo
end = datetime.utcnow()
start = end - timedelta(hours=hours_back)

# Crear CSV
with open("cpu_metrics.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ServiceName", "Timestamp", "CPUUtilization"])

    for svc in services:
        svc_name = svc["serviceName"]

        resp = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "cpuUsage",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ECS",
                            "MetricName": "CPUUtilization",
                            "Dimensions": [
                                {"Name": "ClusterName", "Value": cluster_name},
                                {"Name": "ServiceName", "Value": svc_name}
                            ]
                        },
                        "Period": 300,   # 5 minutos
                        "Stat": "Average"
                    },
                    "ReturnData": True
                }
            ],
            StartTime=start,
            EndTime=end
        )

        results = resp["MetricDataResults"][0]
        for ts, val in zip(results["Timestamps"], results["Values"]):
            writer.writerow([svc_name, ts.isoformat(), val])

print("✅ Métricas exportadas a cpu_metrics.csv")