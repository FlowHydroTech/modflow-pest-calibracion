#!/usr/bin/env python3
"""
Respalda los logs de CloudWatch a archivos CSV.

Uso:
  python backup_logs.py                    # Exporta todos los logs disponibles
  python backup_logs.py --desde 2026-08-01 # Desde una fecha específica
  python backup_logs.py --horas 24         # Solo las últimas N horas
"""

import boto3
import csv
import sys
import os
import glob
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False


# -----------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------
AWS_REGION   = "us-east-1"
LOG_GROUPS   = [
    "/batch/pest-talabre-linux-agents",
    "/batch/pest-talabre-linux-master",
]
OUTPUT_DIR          = "logs_backup"
AGENT_LOG_GROUP     = "/batch/pest-talabre-linux-agents"


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_streams_terminados(output_dir: str) -> set[str]:
    """Lee el ultimo reporte Excel de agentes y retorna el set de log_streams
    con termino == 'SI' (ya completados -> no descargar de nuevo)."""
    if not PANDAS_OK:
        return set()
    pattern = os.path.join(output_dir, "reporte_batch_pest-cmdic-linux-ensi-agents_*.xlsx")
    files = glob.glob(pattern)
    if not files:
        print(f"{ts()} Sin reporte previo de agentes. Se descargaran todos los streams.")
        return set()
    latest = max(files, key=os.path.getmtime)
    print(f"{ts()} Reporte previo encontrado: {os.path.basename(latest)}")
    try:
        df = pd.read_excel(latest, sheet_name="Agentes")
        terminados = set(df.loc[df["termino"] == "SI", "log_stream"].dropna())
        print(f"{ts()} Streams ya terminados en reporte: {len(terminados)} (se omitiran)")
        return terminados
    except Exception as e:
        print(f"{ts()} Error leyendo reporte: {e}. Se descargaran todos los streams.")
        return set()


def parse_args():
    start_ms = None
    if "--horas" in sys.argv:
        idx = sys.argv.index("--horas")
        horas = int(sys.argv[idx + 1])
        start_dt = datetime.now(tz=timezone.utc) - timedelta(hours=horas)
        start_ms = int(start_dt.timestamp() * 1000)
        print(f"{ts()} Filtrando desde las últimas {horas} horas ({start_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
    elif "--desde" in sys.argv:
        idx = sys.argv.index("--desde")
        fecha = sys.argv[idx + 1]
        start_dt = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_ms = int(start_dt.timestamp() * 1000)
        print(f"{ts()} Filtrando desde {fecha} UTC")
    else:
        print(f"{ts()} Exportando todos los logs disponibles")
    return start_ms


def get_log_streams(client, log_group: str) -> list[str]:
    """Lista todos los log streams del grupo."""
    streams = []
    next_token = None
    while True:
        kwargs = {"logGroupName": log_group, "orderBy": "LastEventTime", "descending": True}
        if next_token:
            kwargs["nextToken"] = next_token
        try:
            response = client.describe_log_streams(**kwargs)
        except ClientError as e:
            print(f"{ts()} Error listando streams de {log_group}: {e}")
            break
        for s in response.get("logStreams", []):
            streams.append(s["logStreamName"])
        next_token = response.get("nextToken")
        if not next_token:
            break
    return streams


def get_events(client, log_group: str, stream: str, start_ms: int | None) -> list[dict]:
    """Lee todos los eventos de un log stream."""
    events = []
    next_token = None
    while True:
        kwargs = {
            "logGroupName":  log_group,
            "logStreamName": stream,
            "startFromHead": True,
        }
        if start_ms:
            kwargs["startTime"] = start_ms
        if next_token:
            kwargs["nextToken"] = next_token
        try:
            response = client.get_log_events(**kwargs)
        except ClientError as e:
            print(f"{ts()}   Error leyendo {stream}: {e}")
            break
        batch = response.get("events", [])
        if not batch:
            break
        for ev in batch:
            dt = datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc)
            events.append({
                "timestamp_utc": dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "log_group":     log_group,
                "log_stream":    stream,
                "message":       ev.get("message", "").strip(),
            })
        nt = response.get("nextForwardToken")
        if not nt or nt == next_token:
            break
        next_token = nt
    return events


def export_log_group(client, log_group: str, start_ms: int | None,
                     output_dir: str, streams_omitir: set = None) -> str:
    """Exporta todos los eventos de un log group a un CSV. Retorna la ruta del archivo."""
    if streams_omitir is None:
        streams_omitir = set()
    group_slug = log_group.lstrip("/").replace("/", "_")
    ts_file    = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename   = os.path.join(output_dir, f"{group_slug}_{ts_file}.csv")

    print(f"{ts()} Exportando {log_group}...")
    streams = get_log_streams(client, log_group)
    print(f"{ts()}   Streams encontrados: {len(streams)}")

    if streams_omitir:
        streams_antes = len(streams)
        streams = [s for s in streams if s not in streams_omitir]
        omitidos = streams_antes - len(streams)
        print(f"{ts()}   Streams omitidos (ya terminados en reporte): {omitidos}")
        print(f"{ts()}   Streams a descargar: {len(streams)}")

    total_rows = 0
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp_utc", "log_group", "log_stream", "message"])
        writer.writeheader()
        for stream in streams:
            events = get_events(client, log_group, stream, start_ms)
            if events:
                writer.writerows(events)
                total_rows += len(events)
                print(f"{ts()}   {stream}: {len(events)} eventos")

    print(f"{ts()}   Total: {total_rows} eventos -> {filename}")
    return filename


def main():
    start_ms = parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Cargar streams ya terminados del ultimo reporte de agentes
    streams_terminados = load_streams_terminados(OUTPUT_DIR)

    client = boto3.client("logs", region_name=AWS_REGION)

    archivos = []
    for log_group in LOG_GROUPS:
        try:
            # Filtrar streams terminados solo para el log group de agentes
            omitir = streams_terminados if log_group == AGENT_LOG_GROUP else set()
            path = export_log_group(client, log_group, start_ms, OUTPUT_DIR, omitir)
            archivos.append(path)
        except Exception as e:
            print(f"{ts()} Error exportando {log_group}: {e}")

    print(f"\n{ts()} Respaldo completado. Archivos generados:")
    for a in archivos:
        print(f"  {a}")


if __name__ == "__main__":
    main()
