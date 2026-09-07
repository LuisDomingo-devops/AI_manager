"""
000_baseline_mark.py
====================
Migracion de baseline: marca el estado inicial del esquema como aplicado.

Esta migracion NO ejecuta ningun DDL. Existe para sincronizar el
MigrationRunner con el estado real de la base de datos, creado
originalmente por los schemas directos (init_*_schema) antes de que
existiera el sistema de migraciones versionadas.

Tablas cubiertas como baseline:
  Core:       user_profile, projects, contacts, assets
  Billing:    invoices, quotes, products, payments, invoice_items, quote_items
  Accounting: pgc_accounts, journal_entries, ledger_entries, fiscal_year_status,
              bank_connections, bank_movements, bank_transfers, subscription_status,
              b2b_invoice_status_history
  AI Memory:  messages, conversation_metadata, session_diary
  Legacy 001: conversations, facts, clients, reconciliation_rules, audit_trail,
              projects_wip, tasks_wip
"""

VERSION = "000"
DESCRIPTION = "Baseline: marca el esquema inicial como aplicado (sin DDL)"


def upgrade(conn) -> None:
    """No-op intencional: el esquema base ya existe via init_*_schema()."""
    pass
