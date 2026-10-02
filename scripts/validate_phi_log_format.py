"""Confirmacion de OQ-03: formato de las lineas de Phi en el log del master.

OQ-03 ya fue resuelto por el estado del arte (docs/auditoria/
23_phi_log_format_research.md). Este script CONFIRMA los patrones fundamentados
contra un log real de CloudWatch antes de activar las alertas de calidad en
produccion (riesgo residual: version de PEST_HP y modo estimation/regularization).

Uso:
  python -m scripts.validate_phi_log_format \
      --log-group /batch/pest-talabre-linux-master \
      --region us-east-1 [--minutes 1440]

Imprime, por cada patron candidato, cuantas coincidencias encontro y hasta 5
ejemplos. El patron con mas coincidencias es el que debe usar la Lambda
ExtractPhi (Fase 3).
"""

from __future__ import annotations

import argparse
import re

from calibration_utils.cloudwatch import fetch_recent_events

# Patrones candidatos derivados de la documentacion oficial de PEST y pyEMU
# (ver docs/auditoria/23_phi_log_format_research.md). PEST_HP usa estos; si se
# migra a PEST++ la fuente preferida es el archivo .iobj CSV.
CANDIDATE_PATTERNS: dict[str, str] = {
    "iteration":        r"OPTIMISATION ITERATION NO\.\s*:\s*(\d+)",
    "starting_phi":     r"[Ss]tarting phi for this iteration\s*:\s*([0-9.Ee+-]+)",
    "lowest_phi":       r"[Ll]owest phi this iteration\s*:\s*([0-9.Ee+-]+)",
    "final_phi":        r"[Ff]inal phi\s*:\s*([0-9.Ee+-]+)",
    "convergence":      r"[Oo]ptimis\w*\s+complete",
    "models_requested": r"model\s+(?:up\s+to\s+)?(\d+)\s+times?",
    # Patrones alternativos (otras versiones / PEST++) para comparar cobertura
    "alt_phi_eq":       r"[Pp]hi\s*=\s*([0-9.Ee+-]+)",
    "alt_current_phi":  r"[Cc]urrent phi\s*=\s*([0-9.Ee+-]+)",
    "alt_objective":    r"[Oo]bjective function value\s*:\s*([0-9.Ee+-]+)",
}


def analyze(events: list[dict]) -> dict[str, list[str]]:
    """Retorna, por patron, la lista de lineas que coincidieron."""
    results: dict[str, list[str]] = {name: [] for name in CANDIDATE_PATTERNS}
    compiled = {name: re.compile(pat) for name, pat in CANDIDATE_PATTERNS.items()}
    for ev in events:
        msg = ev.get("message", "")
        for name, rx in compiled.items():
            if rx.search(msg):
                results[name].append(msg.strip())
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confirmar formato de Phi en logs del master")
    parser.add_argument("--log-group", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--minutes", type=int, default=1440, help="Ventana de tiempo (min)")
    args = parser.parse_args(argv)

    print(f"Descargando eventos de {args.log_group} (ultimos {args.minutes} min)...")
    events = fetch_recent_events(args.log_group, minutes=args.minutes, region=args.region)
    print(f"Eventos recuperados: {len(events)}\n")

    results = analyze(events)
    print(f"{'patron':<20} {'matches':>8}   ejemplos")
    print("-" * 70)
    best = None
    best_count = -1
    for name, matches in results.items():
        count = len(matches)
        if name in ("starting_phi", "lowest_phi", "final_phi", "alt_phi_eq",
                    "alt_current_phi", "alt_objective") and count > best_count:
            best, best_count = name, count
        print(f"{name:<20} {count:>8}")
        for ex in matches[:5]:
            print(f"    | {ex[:90]}")

    print("\n" + "=" * 70)
    if best_count > 0:
        print(f"Patron de Phi con mas coincidencias: '{best}' ({best_count} matches).")
        print("Usar este patron en la Lambda ExtractPhi (Fase 3) si difiere del default.")
    else:
        print("ADVERTENCIA: ningun patron de Phi coincidio. Revisar la version de")
        print("PEST_HP (OQ-05) y el modo del .pst (estimation vs regularization, OQ-09).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())