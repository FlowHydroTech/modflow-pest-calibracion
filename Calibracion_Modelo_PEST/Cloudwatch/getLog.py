# Python
import argparse
import boto3
import pandas as pd
from datetime import datetime, timezone
import sys

def parse_iso(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
    raise ValueError("Formato de fecha inválido. Usa YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS")

def clean_message(msg):
    """Elimina caracteres no permitidos en Excel (caracteres de control)."""
    if not msg:
        return msg
    # Eliminar caracteres de control excepto tab, newline, carriage return
    import unicodedata
    cleaned = "".join(
        ch if unicodedata.category(ch)[0] != "C" or ch in ("\t", "\n", "\r")
        else "" for ch in msg
    )
    return cleaned.strip()

def fetch_events(client, log_group, start_ms=None, end_ms=None):
    paginator = client.get_paginator('filter_log_events')
    kwargs = {"logGroupName": log_group, "interleaved": True}
    if start_ms: kwargs["startTime"] = start_ms
    if end_ms: kwargs["endTime"] = end_ms

    rows = []
    for page in paginator.paginate(**kwargs):
        for ev in page.get("events", []):
            rows.append({
                "timestamp": datetime.fromtimestamp(ev["timestamp"]/1000, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "ingestionTime": datetime.fromtimestamp(ev["ingestionTime"]/1000, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "logStreamName": ev.get("logStreamName"),
                "eventId": ev.get("eventId"),
                "message": clean_message(ev.get("message"))
            })
    return rows

def main():
    p = argparse.ArgumentParser(description="Descargar logs CloudWatch a Excel")
    p.add_argument("--log-group", required=True, help="Nombre del log group (ej. /ecs/pest-talabre/hosts)")
    p.add_argument("--region", default=None, help="Región AWS (usa la configuración por defecto si no se provee)")
    p.add_argument("--start", default=None, help="Inicio (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)")
    p.add_argument("--end", default=None, help="Fin (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)")
    p.add_argument("--output", default="cloudwatch_logs.csv", help="Archivo CSV de salida (default: cloudwatch_logs.csv)")
    p.add_argument("--format", choices=["csv", "excel"], default="csv", help="Formato de salida (csv o excel)")
    args = p.parse_args()

    start_ms = parse_iso(args.start) if args.start else None
    end_ms = parse_iso(args.end) if args.end else None

    client = boto3.client("logs", region_name=args.region) if args.region else boto3.client("logs")
    print(f"Descargando eventos del log group '{args.log_group}'...")
    rows = fetch_events(client, args.log_group, start_ms, end_ms)

    if not rows:
        print("No se encontraron eventos para los parámetros indicados.", file=sys.stderr)
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("timestamp")
    
    if args.format == "excel":
        try:
            df.to_excel(args.output, index=False, engine="openpyxl")
        except:
            
            print("Error: Para exportar a Excel, demasiadas filas para el formato Excel. Se genera descarga en formato CSV.", file=sys.stderr)
            df.to_csv(args.output.rsplit('.', 1)[0] + ".csv", index=False, encoding="utf-8")
            return
    else:
        df.to_csv(args.output, index=False, encoding="utf-8")
    
    print(f"Exportado {len(df)} eventos a {args.output}")

if __name__ == "__main__":
    main()