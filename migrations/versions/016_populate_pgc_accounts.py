def upgrade(conn):
    accounts = [
        ("43000000", "Clientes", "activo"),
        ("40000000", "Proveedores", "pasivo"),
        ("70500000", "Prestacion de Servicios", "ingreso"),
        ("62900000", "Gastos Diversos", "gasto"),
        ("47700021", "IVA Repercutido 21%", "pasivo"),
        ("47200021", "IVA Soportado 21%", "activo"),
        ("47300000", "H.P. Retenciones y pagos a cuenta", "activo"),
        ("47510000", "H.P. Acreedora por retenciones practicadas", "pasivo"),
        ("57200000", "Bancos c/c", "activo"),
        ("12900000", "Resultado del ejercicio", "patrimonio")
    ]
    for code, name, type_ in accounts:
        conn.execute(
            "INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES (?, ?, ?)",
            (code, name, type_)
        )

def downgrade(conn):
    # No eliminamos cuentas para evitar romper referencialidad
    pass
