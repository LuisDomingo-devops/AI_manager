import pdfplumber

def dump():
    pdf_path = "C:/Users/luisd/Desktop/Facturas_Para_Procesar/Factura julio 2026-- pendiente de pago.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\n--- PÁGINA {i+1} ---")
            print(page.extract_text())

if __name__ == "__main__":
    dump()
