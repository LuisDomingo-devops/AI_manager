"""
HERRAMIENTA CLI PRIVADA DE ADMINISTRACIÓN DE LICENCIAS — ALFONSO AUTÓNOMO
(SOLO PARA USO INTERNO DEL CREADOR / ADMINISTRADOR)

Uso:
python license_admin_cli.py issue --holder "Pedro Perez" --client-id "pedro_01" --machine-fp "ALF-MACH-XXXX" --months 1
python license_admin_cli.py trial --holder "Ana Gomez" --machine-fp "ALF-MACH-YYYY"
"""

import sys
import json
import argparse
from pathlib import Path

# Añadir raíz al sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from admin_tools_private.license_issuer import PrivateLicenseIssuer

def main():
    parser = argparse.ArgumentParser(description="Emisor Privado de Licencias Alfonso Autónomo")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Comando 'issue' (Licencia mensual)
    p_issue = subparsers.add_parser("issue", help="Emitir licencia mensual de pago")
    p_issue.add_argument("--holder", required=True, help="Nombre o Razón Social del autónomo")
    p_issue.add_argument("--client-id", required=True, help="ID único de cliente/tenant")
    p_issue.add_argument("--machine-fp", required=True, help="Huella digital de hardware (Machine Fingerprint)")
    p_issue.add_argument("--months", type=int, default=1, help="Número de meses de vigencia (default: 1)")
    p_issue.add_argument("--out", default="license.lic", help="Archivo de salida (default: license.lic)")

    # Comando 'trial' (Prueba gratuita de 14 días)
    p_trial = subparsers.add_parser("trial", help="Emitir licencia de prueba de 14 días")
    p_trial.add_argument("--holder", required=True, help="Nombre del usuario de prueba")
    p_trial.add_argument("--machine-fp", required=True, help="Huella digital de hardware")
    p_trial.add_argument("--days", type=int, default=14, help="Días de prueba (default: 14)")
    p_trial.add_argument("--out", default="license.lic", help="Archivo de salida")

    # Comando 'transfer' (Cambio de ordenador)
    p_trans = subparsers.add_parser("transfer", help="Transferir licencia existente a un nuevo ordenador")
    p_trans.add_argument("--license-file", required=True, help="Archivo license.lic original")
    p_trans.add_argument("--new-machine-fp", required=True, help="Nueva huella de hardware del cliente")
    p_trans.add_argument("--out", default="license_transferred.lic", help="Archivo de salida")

    args = parser.parse_args()

    if args.command == "issue":
        lic = PrivateLicenseIssuer.issue_paid_license(
            holder=args.holder,
            client_id=args.client_id,
            machine_fingerprint=args.machine_fp,
            months=args.months
        )
        Path(args.out).write_text(json.dumps(lic, indent=2), encoding="utf-8")
        print(f"[+] Licencia de pago emitida con éxito para '{args.holder}' (vence el {lic['expires_at']})")
        print(f"[+] Guardada en: {args.out}")

    elif args.command == "trial":
        lic = PrivateLicenseIssuer.issue_trial_license(
            holder=args.holder,
            machine_fingerprint=args.machine_fp,
            days=args.days
        )
        Path(args.out).write_text(json.dumps(lic, indent=2), encoding="utf-8")
        print(f"[+] Licencia de prueba de {args.days} días emitida con éxito (vence el {lic['expires_at']})")
        print(f"[+] Guardada en: {args.out}")

    elif args.command == "transfer":
        orig_data = json.loads(Path(args.license_file).read_text(encoding="utf-8"))
        trans_lic = PrivateLicenseIssuer.transfer_license(
            existing_license=orig_data,
            new_machine_fingerprint=args.new_machine_fp
        )
        Path(args.out).write_text(json.dumps(trans_lic, indent=2), encoding="utf-8")
        print(f"[+] Licencia transferida exitosamente al nuevo hardware: {args.new_machine_fp}")
        print(f"[+] Guardada en: {args.out}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
