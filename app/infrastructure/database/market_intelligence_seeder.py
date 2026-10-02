"""
market_intelligence_seeder.py
==============================
Sembrador e inicializador de tablas para el Módulo 8:
- market_sector_benchmarks_cache: Caché local persistente con TTL de 30 días para datos sectoriales de mercado.
- strategic_dafo_reports: Histórico auditable de diagnósticos estratégicos DAFO emitidos.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


class MarketIntelligenceSeeder:
    """Inicializador de tablas para inteligencia de mercado y análisis estratégico."""

    SCHEMA_STATEMENTS = [
        """
        CREATE TABLE IF NOT EXISTS market_sector_benchmarks_cache (
            cnae_code TEXT NOT NULL,
            region TEXT NOT NULL,
            sector_name TEXT NOT NULL,
            p25_price TEXT NOT NULL,
            p50_price TEXT NOT NULL,
            p75_price TEXT NOT NULL,
            average_price TEXT NOT NULL,
            inflation_rate TEXT NOT NULL,
            source TEXT NOT NULL,
            cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ttl_days INTEGER NOT NULL DEFAULT 30,
            PRIMARY KEY (cnae_code, region)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS strategic_dafo_reports (
            report_id TEXT PRIMARY KEY,
            fiscal_year INTEGER NOT NULL,
            cnae_code TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            client_concentration_ratio TEXT NOT NULL,
            high_concentration_alert INTEGER NOT NULL,
            supplier_cost_increase_rate TEXT NOT NULL,
            runway_months TEXT NOT NULL,
            price_percentile INTEGER NOT NULL,
            dafo_payload_json TEXT NOT NULL,
            anonymization_verified INTEGER NOT NULL DEFAULT 1
        );
        """
    ]

    @classmethod
    def init_tables(cls, conn: sqlite3.Connection) -> None:
        """Crea las tablas necesarias en la base de datos si no existen."""
        cursor = conn.cursor()
        for stmt in cls.SCHEMA_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()
        logger.info("Tablas de inteligencia de mercado y reportes DAFO inicializadas correctamente.")
