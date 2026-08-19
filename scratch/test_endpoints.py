import httpx

cert = "data/certificados_prueba/certificado_pruebas.pem"
key = "data/certificados_prueba/clave_pruebas.pem"

url_pre1 = "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP"
url_pre10 = "https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP"

headers = {"Content-Type": "text/xml; charset=utf-8"}
soap_dummy = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body><test/></soapenv:Body></soapenv:Envelope>'

print("--- Probando prewww1 ---")
try:
    with httpx.Client(cert=(cert, key), verify=True, timeout=10) as c:
        r = c.post(url_pre1, content=soap_dummy, headers=headers)
        print("Status:", r.status_code)
        print("Headers:", dict(r.headers))
        print("Text:", r.text[:300])
except Exception as e:
    print("Error prewww1:", e)

print("\n--- Probando prewww10 ---")
try:
    with httpx.Client(cert=(cert, key), verify=True, timeout=10) as c:
        r = c.post(url_pre10, content=soap_dummy, headers=headers)
        print("Status:", r.status_code)
        print("Headers:", dict(r.headers))
        print("Text:", r.text[:300])
except Exception as e:
    print("Error prewww10:", e)
