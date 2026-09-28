#!/usr/bin/env python3
"""
Script de Auditoría AST de Sentencias 'pass'
Analiza archivos Python y reporta con precisión el conteo y líneas de 'pass' huérfanos.
"""

import ast
import sys
from pathlib import Path

def audit_file(filepath: Path) -> list[int]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    tree = ast.parse(content, filename=str(filepath))
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Pass)]

def main():
    target_files = [
        "tests/backend/qa/test_qa_stress.py",
        "tests/backend/integration/test_integration_stress.py",
        "tests/backend/integration/test_coverage_booster.py",
        "app/utils/dev_seeder.py",
        "app/utils/legal_seeder.py",
    ]
    
    if len(sys.argv) > 1:
        target_files = sys.argv[1:]
        
    print("=== REPORTE DE AUDITORÍA AST DE SENTENCIAS 'pass' ===")
    total = 0
    for rel_path in target_files:
        p = Path(rel_path)
        if not p.exists():
            print(f"[-] {rel_path}: ARCHIVO NO ENCONTRADO")
            continue
        passes = audit_file(p)
        total += len(passes)
        print(f"[*] {rel_path}: {len(passes)} sentencias 'pass' (líneas: {passes[:10]}{'...' if len(passes) > 10 else ''})")
        
    print("=" * 55)
    print(f"TOTAL DETECTADO EN OBJETIVOS: {total} sentencias 'pass'")
    return total

if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
