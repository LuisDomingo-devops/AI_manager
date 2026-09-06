prompt_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\prompts\chat_system.txt'
with open(prompt_path, 'a', encoding='utf-8') as f:
    f.write("\n\nINSTRUCCIÓN CRÍTICA DE OPTIMIZACIÓN:\nSi el usuario hace preguntas amplias o comparativas sobre impuestos, gastos o contabilidad de un año entero (ej. 'cuánto iva he pagado', 'muéstrame la evolución de gastos', 'cuánto llevo este año'), DEBES usar OBLIGATORIAMENTE la macro-herramienta 'get_full_financial_report' en lugar de llamar a agregados o libro diario por separado, para ahorrar turnos y mejorar la latencia.\n")
