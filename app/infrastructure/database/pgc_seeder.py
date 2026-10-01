"""
Sembrador del Plan General Contable (PGC Pymes).
Asegura la carga de cuentas estándar con ortografía limpia en castellano sin caracteres corruptos.
"""

import sqlite3
from typing import List, Tuple


class PgcSeeder:
    """Siembra y actualiza el cuadro de cuentas oficial del PGC Pymes."""

    PGC_ACCOUNTS: List[Tuple[str, str, str]] = [
        # Grupo 1: Financiación básica
        ("10000000", "Capital social", "patrimonio"),
        ("12900000", "Resultado del ejercicio", "patrimonio"),

        # Grupo 2: Inmovilizado y Amortizaciones
        ("21300000", "Maquinaria", "activo"),
        ("21600000", "Mobiliario", "activo"),
        ("21700000", "Equipos para procesos de información", "activo"),
        ("28100000", "Amortización acumulada del inmovilizado material", "activo"),

        # Grupo 4: Acreedores y Deudores
        ("40000000", "Proveedores", "pasivo"),
        ("41000000", "Acreedores por prestaciones de servicios", "pasivo"),
        ("43000000", "Clientes", "activo"),
        ("47200004", "IVA Soportado 4%", "activo"),
        ("47200010", "IVA Soportado 10%", "activo"),
        ("47200021", "IVA Soportado 21%", "activo"),
        ("47300000", "H.P. Retenciones y pagos a cuenta", "activo"),
        ("47510000", "H.P. Acreedora por retenciones practicadas", "pasivo"),
        ("47700004", "IVA Repercutido 4%", "pasivo"),
        ("47700010", "IVA Repercutido 10%", "pasivo"),
        ("47700021", "IVA Repercutido 21%", "pasivo"),

        # Grupo 5: Cuentas financieras
        ("57000000", "Caja, euros", "activo"),
        ("57200000", "Bancos e instituciones de crédito c/c", "activo"),

        # Grupo 6: Compras y Gastos
        ("60000000", "Compras de mercaderías", "gasto"),
        ("62100000", "Arrendamientos y cánones", "gasto"),
        ("62800000", "Suministros (electricidad, agua, gas)", "gasto"),
        ("62900000", "Otros servicios y gastos diversos", "gasto"),
        ("64000000", "Sueldos y salarios", "gasto"),
        ("64200000", "Seguridad Social a cargo de la empresa", "gasto"),
        ("68100000", "Amortización del inmovilizado material", "gasto"),

        # Grupo 7: Ventas e Ingresos
        ("70000000", "Ventas de mercaderías", "ingreso"),
        ("70500000", "Prestación de servicios", "ingreso")
    ]

    @classmethod
    def seed_accounts(cls, conn: sqlite3.Connection):
        """Inserta o actualiza las cuentas del PGC sin duplicados."""
        cursor = conn.cursor()
        for code, name, type_ in cls.PGC_ACCOUNTS:
            cursor.execute(
                """
                INSERT INTO pgc_accounts (code, name, type) 
                VALUES (?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET name=excluded.name, type=excluded.type
                """,
                (code, name, type_)
            )
        conn.commit()
