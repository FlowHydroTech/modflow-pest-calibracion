#!/usr/bin/env python3
"""
Script para consolidar logs de Excel de CloudWatch
Lee todos los archivos .xlsx de la carpeta log/
Consolida en un dataframe único y exporta a CSV
"""

import pandas as pd
import os
from pathlib import Path

def main():
    # Definir rutas
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'log')
    
    # Verificar que la carpeta log existe
    if not os.path.exists(log_dir):
        print(f"ERROR: La carpeta '{log_dir}' no existe")
        return
    
    # Buscar todos los archivos .xlsx
    xlsx_files = list(Path(log_dir).glob('*.xlsx'))
    
    if not xlsx_files:
        print(f"ADVERTENCIA: No se encontraron archivos .xlsx en {log_dir}")
        return
    
    print(f"Encontrados {len(xlsx_files)} archivo(s) .xlsx")
    
    # Consolidar todos los dataframes
    all_dfs = []
    
    for xlsx_file in xlsx_files:
        print(f"Leyendo {xlsx_file.name}...")
        try:
            # Leer el archivo Excel
            df = pd.read_excel(xlsx_file)
            
            # Agregar columna con el nombre del archivo de origen
            df['source_file'] = xlsx_file.name
            
            # Agregar a la lista
            all_dfs.append(df)
            print(f"  ✓ Cargado: {len(df)} registros")
            
        except Exception as e:
            print(f"  ✗ Error al leer {xlsx_file.name}: {e}")
            continue
    
    if not all_dfs:
        print("ERROR: No se pudieron cargar archivos")
        return
    
    # Consolidar todos los dataframes en uno solo
    print("\nConsolidando dataframes...")
    consolidated_df = pd.concat(all_dfs, ignore_index=True)
    print(f"Total de registros: {len(consolidated_df)}")
    print(f"Columnas: {list(consolidated_df.columns)}")
    
    # Exportar el dataframe completo a CSV
    resumen_csv = os.path.join(script_dir, 'resumen.csv')
    consolidated_df.to_csv(resumen_csv, index=False, encoding='utf-8')
    print(f"\n✓ Archivo exportado: {resumen_csv}")
    
    # Filtrar registros con el error específico de Wine
    wine_error = "wine: failed to map the shared user data: c0000018"
    
    if 'message' in consolidated_df.columns:
        error_df = consolidated_df[
            consolidated_df['message'].str.contains(wine_error, case=False, na=False)
        ]
        
        if len(error_df) > 0:
            error_csv = os.path.join(script_dir, 'wine_errors_c0000018.csv')
            error_df.to_csv(error_csv, index=False, encoding='utf-8')
            print(f"✓ Archivo de errores exportado: {error_csv}")
            print(f"  Total de registros con error c0000018: {len(error_df)}")
            
            # Mostrar estadísticas
            print(f"\nEstadísticas del error c0000018:")
            if 'source_file' in error_df.columns and 'logStreamName' in consolidated_df.columns:
                print(f"\nAgentes afectados por archivo de origen:")
                print(f"{'Archivo':<50} {'Agentes':<10} {'Total':<10} {'Porcentaje':<12}")
                print(f"{'-'*82}")
                
                # Obtener archivos únicos en los datos
                unique_files = consolidated_df['source_file'].unique()
                
                for file_name in unique_files:
                    # Total de logStreamName distintos en este archivo
                    file_data = consolidated_df[consolidated_df['source_file'] == file_name]
                    total_streams = file_data['logStreamName'].nunique()
                    
                    # logStreamName distintos con el error en este archivo
                    file_errors = error_df[error_df['source_file'] == file_name]
                    error_streams = file_errors['logStreamName'].nunique()
                    
                    if total_streams > 0:
                        percentage = (error_streams / total_streams) * 100
                        print(f"{file_name:<50} {error_streams:<10} {total_streams:<10} {percentage:>6.2f}%")
            elif 'source_file' in error_df.columns:
                print(f"\nADVERTENCIA: La columna 'logStreamName' no existe en los datos")
                print(f"Mostrando estadísticas por registros:")
                print(error_df['source_file'].value_counts().to_string())
        else:
            print(f"\nℹ No se encontraron registros con el error: '{wine_error}'")
    else:
        print(f"\nADVERTENCIA: La columna 'message' no existe en los datos")
        print(f"Columnas disponibles: {list(consolidated_df.columns)}")
    
    # Mostrar información del dataframe consolidado
    print(f"\n{'='*60}")
    print(f"RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"Total de registros: {len(consolidated_df)}")
    print(f"Total de archivos procesados: {len(xlsx_files)}")
    print(f"Archivos:")
    for xlsx_file in xlsx_files:
        print(f"  - {xlsx_file.name}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
