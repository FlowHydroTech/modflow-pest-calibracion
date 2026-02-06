import pandas as pd

# Leer el CSV
csv_file = 'mod_res_ensi_west2_agentes_logs20260202_0845.csv'
df = pd.read_csv(csv_file)

# Contar logStreamName únicos
unique_streams = df['logStreamName'].nunique()
total_rows = len(df)

print(f"📊 Análisis de LogStream")
print(f"=" * 50)
print(f"Archivo: {csv_file}")
print(f"Total de filas: {total_rows}")
print(f"LogStreamName únicos: {unique_streams}")
print(f"\n🔍 Detalle de cada logStreamName:")
print(f"=" * 50)

# Mostrar conteo por cada logStreamName
# stream_counts = df['logStreamName'].value_counts()
# for stream, count in stream_counts.items():
#     print(f"{stream}: {count} registros")

# Resumen
print(f"\n✅ Completado")