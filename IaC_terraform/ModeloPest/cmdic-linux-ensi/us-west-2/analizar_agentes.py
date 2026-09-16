"""Analiza TODOS los CSVs de logs de agentes (batch_pest-cmdic-linux-ensi-agents_*.csv),
los combina y deduplica, luego genera un reporte Excel con estadísticas por log_stream.

Uso:
  python analizar_agentes.py                          # Usa TODOS los CSVs en logs_backup/
  python analizar_agentes.py --archivo mi_archivo.csv # Usa un archivo específico

Columnas del reporte:
  log_stream        : nombre del stream (agent/default/<taskId>)
  task_id           : ID de la tarea ECS
  fecha_inicio      : timestamp del primer evento con "Running model"
  fecha_termino     : timestamp del último evento con "Model run complete"
  tiempo_ejecucion  : diferencia fecha_termino - fecha_inicio (HH:MM:SS)
  inicio            : SI / NO - si tiene mensaje "Running model"
  termino           : SI / NO - si tiene mensaje "Model run complete"
  con_alerta        : SI / NO - si algún mensaje contiene palabras de warning/error/fail
  total_eventos     : cantidad total de eventos del stream
  alertas_detalle   : primeras palabras de alerta encontradas (hasta 3)
"""

import os
import sys
import glob
import pandas as pd
from datetime import datetime, timedelta


# -----------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------
LOGS_DIR         = "logs_backup"
OUTPUT_DIR       = "logs_backup"
MSG_START        = "Running model"
MSG_END          = "Model run complete"
ALERT_KEYWORDS   = ["warning", "warn", "error", "fail", "failed", "failure",
                    "exception", "traceback", "critical", "fatal", "abort",
                    "cannot", "unable", "timeout", "timed out", "refused"]


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def find_latest_csv(directory: str) -> str | None:
    """Busca el CSV de agentes más reciente en el directorio."""
    pattern = os.path.join(directory, "batch_pest-cmdic-linux-ensi-agents_*.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_all_csvs(directory: str) -> pd.DataFrame:
    """Lee TODOS los CSVs de agentes, los combina y deduplica por todas las columnas."""
    pattern = os.path.join(directory, "batch_pest-cmdic-linux-ensi-agents_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"{ts()} No se encontraron archivos CSV en {directory}/")
        return pd.DataFrame()
    
    print(f"{ts()} CSVs encontrados: {len(files)}")
    df_combined = pd.DataFrame()
    
    for csv_file in files:
        try:
            df = pd.read_csv(csv_file)
            df_combined = pd.concat([df_combined, df], ignore_index=True)
            print(f"{ts()}   Leido: {os.path.basename(csv_file)} ({len(df):,} filas)")
        except Exception as e:
            print(f"{ts()}   Error leyendo {os.path.basename(csv_file)}: {e}")
    
    if df_combined.empty:
        print(f"{ts()} No hay datos en los CSVs.")
        return df_combined
    
    filas_antes = len(df_combined)
    # Deduplicar por TODAS las columnas
    df_combined = df_combined.drop_duplicates()
    filas_despues = len(df_combined)
    duplicados = filas_antes - filas_despues
    
    print(f"{ts()} Total filas combinadas: {filas_antes:,}")
    print(f"{ts()} Duplicados removidos: {duplicados:,}")
    print(f"{ts()} Registros unicos: {filas_despues:,}")
    print(f"{ts()} Streams unicos: {df_combined['log_stream'].nunique():,}")
    
    return df_combined


def tiene_alerta(messages: pd.Series) -> tuple[bool, str]:
    """Verifica si algún mensaje contiene palabras de alerta.
    
    Retorna (bool, detalle) donde detalle son los primeros mensajes con alerta.
    """
    alertas = []
    for msg in messages.dropna():
        msg_lower = str(msg).lower()
        for kw in ALERT_KEYWORDS:
            if kw in msg_lower:
                # Tomar los primeros 80 caracteres del mensaje
                resumen = str(msg).strip()[:80]
                if resumen not in alertas:
                    alertas.append(resumen)
                break
        if len(alertas) >= 3:
            break
    return (len(alertas) > 0, " | ".join(alertas))


def analizar(df: pd.DataFrame) -> pd.DataFrame:
    """Genera el DataFrame de análisis por log_stream desde los datos cargados."""
    print(f"{ts()} Analizando {len(df):,} eventos de {df['log_stream'].nunique():,} streams...")

    # Parsear timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")

    # Extraer task_id del log_stream (último componente)
    df["task_id"] = df["log_stream"].str.split("/").str[-1]

    resultados = []

    for stream, grupo in df.groupby("log_stream"):
        grupo = grupo.sort_values("timestamp")
        messages = grupo["message"]
        task_id  = stream.split("/")[-1]

        # Inicio y término
        mask_start = messages.str.contains(MSG_START, case=False, na=False)
        mask_end   = messages.str.contains(MSG_END,   case=False, na=False)

        tiene_inicio  = mask_start.any()
        tiene_termino = mask_end.any()

        fecha_inicio  = grupo.loc[mask_start, "timestamp"].min() if tiene_inicio  else pd.NaT
        fecha_termino = grupo.loc[mask_end,   "timestamp"].max() if tiene_termino else pd.NaT

        # Tiempo de ejecución
        horas_ejecucion = None
        if pd.notna(fecha_inicio) and pd.notna(fecha_termino) and fecha_termino >= fecha_inicio:
            delta = fecha_termino - fecha_inicio
            total_seg = int(delta.total_seconds())
            hh = total_seg // 3600
            mm = (total_seg % 3600) // 60
            ss = total_seg % 60
            tiempo_ejecucion = f"{hh:02d}:{mm:02d}:{ss:02d}"
            horas_ejecucion  = round(delta.total_seconds() / 3600, 2)
        else:
            tiempo_ejecucion = ""

        # Alertas
        hay_alerta, alerta_detalle = tiene_alerta(messages)

        resultados.append({
            "log_stream":       stream,
            "task_id":          task_id,
            "fecha_inicio":     fecha_inicio.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(fecha_inicio)  else "",
            "fecha_termino":    fecha_termino.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(fecha_termino) else "",
            "tiempo_ejecucion": tiempo_ejecucion,
            "horas":            horas_ejecucion,
            "inicio":           "SI" if tiene_inicio  else "NO",
            "termino":          "SI" if tiene_termino else "NO",
            "con_alerta":       "SI" if hay_alerta    else "NO",
            "total_eventos":    len(grupo),
            "alertas_detalle":  alerta_detalle,
        })

    df_result = pd.DataFrame(resultados)

    # Ordenar: primero los que tienen alerta, luego por fecha_inicio desc
    df_result["_sort_alerta"] = (df_result["con_alerta"] == "SI").astype(int)
    df_result = df_result.sort_values(
        ["_sort_alerta", "fecha_inicio"],
        ascending=[False, False]
    ).drop(columns=["_sort_alerta"])

    return df_result


def exportar_excel(df: pd.DataFrame, output_path: str) -> None:
    """Exporta el DataFrame a Excel con formato."""
    from openpyxl.styles import PatternFill, Font, Alignment

    # --- Calcular resumen ---
    total      = len(df)
    iniciados  = (df["inicio"]     == "SI").sum()
    terminados = (df["termino"]    == "SI").sum()
    alertas    = (df["con_alerta"] == "SI").sum()
    horas_vals = df["horas"].dropna()
    horas_prom = round(horas_vals.mean(), 2) if len(horas_vals) > 0 else ""
    horas_min  = round(horas_vals.min(),  2) if len(horas_vals) > 0 else ""
    horas_max  = round(horas_vals.max(),  2) if len(horas_vals) > 0 else ""

    df_resumen = pd.DataFrame([
        {"Metrica": "Total agentes (streams)",   "Valor": total},
        {"Metrica": "Con inicio (Running model)",  "Valor": iniciados},
        {"Metrica": "Con termino (Model run complete)", "Valor": terminados},
        {"Metrica": "Sin terminar",               "Valor": total - terminados},
        {"Metrica": "Con alerta",                 "Valor": alertas},
        {"Metrica": "Horas promedio ejecucion",   "Valor": horas_prom},
        {"Metrica": "Horas minimas ejecucion",    "Valor": horas_min},
        {"Metrica": "Horas maximas ejecucion",    "Valor": horas_max},
    ])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # --- Hoja Resumen ---
        df_resumen.to_excel(writer, index=False, sheet_name="Resumen")
        ws_res = writer.sheets["Resumen"]

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in ws_res[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        ws_res.column_dimensions["A"].width = 38
        ws_res.column_dimensions["B"].width = 18

        alerta_fill_res = PatternFill(start_color="FFD7D7", end_color="FFD7D7", fill_type="solid")
        ok_fill_res     = PatternFill(start_color="D7FFD7", end_color="D7FFD7", fill_type="solid")
        for row in ws_res.iter_rows(min_row=2, max_row=ws_res.max_row):
            metrica = str(row[0].value or "")
            if "alerta" in metrica.lower():
                fill = alerta_fill_res
            elif "termino" in metrica.lower() or "promedio" in metrica.lower() or "maxima" in metrica.lower() or "minima" in metrica.lower():
                fill = ok_fill_res
            else:
                fill = PatternFill(fill_type=None)
            for cell in row:
                if fill.fill_type:
                    cell.fill = fill
                cell.font = Font(bold=("Total" in str(row[0].value or "")))

        # --- Hoja Agentes ---
        df.to_excel(writer, index=False, sheet_name="Agentes")
        ws = writer.sheets["Agentes"]

        col_widths = {
            "log_stream":       55,
            "task_id":          36,
            "fecha_inicio":     22,
            "fecha_termino":    22,
            "tiempo_ejecucion": 18,
            "horas":            10,
            "inicio":           10,
            "termino":          10,
            "con_alerta":       12,
            "total_eventos":    15,
            "alertas_detalle":  80,
        }
        for i, col in enumerate(df.columns, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = col_widths.get(col, 20)

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        alerta_fill  = PatternFill(start_color="FFD7D7", end_color="FFD7D7", fill_type="solid")
        ok_fill      = PatternFill(start_color="D7FFD7", end_color="D7FFD7", fill_type="solid")
        pending_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")

        col_alerta  = df.columns.get_loc("con_alerta") + 1
        col_termino = df.columns.get_loc("termino")    + 1

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            alerta_val  = row[col_alerta  - 1].value
            termino_val = row[col_termino - 1].value
            if alerta_val == "SI":
                fill = alerta_fill
            elif termino_val == "SI":
                fill = ok_fill
            else:
                fill = pending_fill
            for cell in row:
                cell.fill = fill

    print(f"{ts()} Reporte exportado: {output_path}")


def main():
    # Cargar datos de entrada
    if "--archivo" in sys.argv:
        # Modo single: usar un archivo específico
        idx = sys.argv.index("--archivo")
        csv_path = sys.argv[idx + 1]
        if not os.path.exists(csv_path):
            print(f"{ts()} Error: archivo no encontrado: {csv_path}")
            sys.exit(1)
        print(f"{ts()} Usando archivo específico: {csv_path}")
        df_raw = pd.read_csv(csv_path)
    else:
        # Modo default: usar TODOS los CSVs con deduplicación
        print(f"{ts()} Modo: TODOS los CSVs con deduplicacion")
        df_raw = load_all_csvs(LOGS_DIR)
        if df_raw.empty:
            print(f"{ts()} Error: sin datos para analizar")
            sys.exit(1)

    # Analizar
    df_result = analizar(df_raw)

    # Resumen en consola
    total     = len(df_result)
    iniciados = (df_result["inicio"]    == "SI").sum()
    terminados= (df_result["termino"]   == "SI").sum()
    alertas   = (df_result["con_alerta"]== "SI").sum()
    print(f"{ts()} Resumen:")
    print(f"{ts()}   Total streams:     {total}")
    print(f"{ts()}   Con inicio:        {iniciados}")
    print(f"{ts()}   Con termino:       {terminados}")
    print(f"{ts()}   Con alerta:        {alertas}")
    print(f"{ts()}   Sin terminar:      {total - terminados}")

    # Exportar a Excel
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name  = os.path.splitext(os.path.basename(csv_path))[0]
    excel_path = os.path.join(OUTPUT_DIR, f"reporte_{base_name}_{ts()}.xlsx")
    exportar_excel(df_result, excel_path)


if __name__ == "__main__":
    main()
