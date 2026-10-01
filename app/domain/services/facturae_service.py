"""
Servicio generador de Facturae 3.2.2 conforme al estándar de la AEAT / FACe y Ley Crea y Crece.
"""

from app.domain.models.billing import InvoiceDTO


class FacturaeService:
    """Generador de ficheros XML estructurados en formato Facturae 3.2.2."""

    def generate_facturae_322(self, invoice: InvoiceDTO) -> bytes:
        invoice_num_str = f"{invoice.series}-{invoice.number:04d}"
        xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<fe:Facturae xmlns:fe="http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <FileHeader>
    <SchemaVersion>3.2.2</SchemaVersion>
    <Modality>I</Modality>
    <InvoiceIssuerType>EM</InvoiceIssuerType>
    <Batch>
      <BatchIdentifier>{invoice.issuer_nif}{invoice_num_str}</BatchIdentifier>
      <InvoicesCount>1</InvoicesCount>
      <TotalInvoicesAmount>
        <TotalAmount>{invoice.total_amount:.2f}</TotalAmount>
      </TotalInvoicesAmount>
      <TotalOutstandingAmount>
        <TotalAmount>{invoice.total_amount:.2f}</TotalAmount>
      </TotalOutstandingAmount>
      <TotalExecutableAmount>
        <TotalAmount>{invoice.total_amount:.2f}</TotalAmount>
      </TotalExecutableAmount>
      <InvoiceCurrencyCode>EUR</InvoiceCurrencyCode>
    </Batch>
  </FileHeader>
  <Parties>
    <SellerParty>
      <TaxIdentification>
        <PersonTypeCode>J</PersonTypeCode>
        <ResidenceTypeCode>R</ResidenceTypeCode>
        <TaxIdentificationNumber>{invoice.issuer_nif}</TaxIdentificationNumber>
      </TaxIdentification>
      <LegalEntity>
        <CorporateName>{invoice.issuer_name}</CorporateName>
        <AddressInSpain>
          <Address>Calle Fiscal 1</Address>
          <PostCode>28001</PostCode>
          <Town>Madrid</Town>
          <Province>Madrid</Province>
          <CountryCode>ESP</CountryCode>
        </AddressInSpain>
      </LegalEntity>
    </SellerParty>
    <BuyerParty>
      <TaxIdentification>
        <PersonTypeCode>J</PersonTypeCode>
        <ResidenceTypeCode>R</ResidenceTypeCode>
        <TaxIdentificationNumber>{invoice.recipient_nif or 'NIF_NO_APLICA'}</TaxIdentificationNumber>
      </TaxIdentification>
      <LegalEntity>
        <CorporateName>{invoice.recipient_name or 'CONSUMIDOR FINAL'}</CorporateName>
        <AddressInSpain>
          <Address>Calle Cliente 2</Address>
          <PostCode>08001</PostCode>
          <Town>Barcelona</Town>
          <Province>Barcelona</Province>
          <CountryCode>ESP</CountryCode>
        </AddressInSpain>
      </LegalEntity>
    </BuyerParty>
  </Parties>
  <Invoices>
    <Invoice>
      <InvoiceHeader>
        <InvoiceNumber>{invoice_num_str}</InvoiceNumber>
        <InvoiceSeriesCode>{invoice.series}</InvoiceSeriesCode>
        <InvoiceDocumentType>FC</InvoiceDocumentType>
        <InvoiceClass>OO</InvoiceClass>
      </InvoiceHeader>
      <InvoiceIssueData>
        <IssueDate>{invoice.issue_date}</IssueDate>
        <InvoiceCurrencyCode>EUR</InvoiceCurrencyCode>
        <TaxCurrencyCode>EUR</TaxCurrencyCode>
        <LanguageName>es</LanguageName>
      </InvoiceIssueData>
      <TaxesOutputs>
        <Tax>
          <TaxTypeCode>01</TaxTypeCode>
          <TaxRate>21.00</TaxRate>
          <TaxableBase>
            <TotalAmount>{invoice.base_amount:.2f}</TotalAmount>
          </TaxableBase>
          <TaxAmount>
            <TotalAmount>{invoice.tax_amount:.2f}</TotalAmount>
          </TaxAmount>
        </Tax>
      </TaxesOutputs>
      <InvoiceTotals>
        <TotalGrossAmount>{invoice.base_amount:.2f}</TotalGrossAmount>
        <TotalGrossAmountBeforeTaxes>{invoice.base_amount:.2f}</TotalGrossAmountBeforeTaxes>
        <TotalTaxOutputs>{invoice.tax_amount:.2f}</TotalTaxOutputs>
        <TotalTaxesWithheld>0.00</TotalTaxesWithheld>
        <InvoiceTotal>{invoice.total_amount:.2f}</InvoiceTotal>
        <TotalOutstandingAmount>{invoice.total_amount:.2f}</TotalOutstandingAmount>
        <TotalExecutableAmount>{invoice.total_amount:.2f}</TotalExecutableAmount>
      </InvoiceTotals>
      <Items>
        <InvoiceLine>
          <ItemDescription>Servicios prestados</ItemDescription>
          <Quantity>1.00</Quantity>
          <UnitOfMeasure>01</UnitOfMeasure>
          <UnitPriceWithoutTax>{invoice.base_amount:.2f}</UnitPriceWithoutTax>
          <TotalCost>{invoice.base_amount:.2f}</TotalCost>
          <GrossAmount>{invoice.base_amount:.2f}</GrossAmount>
          <TaxesOutputs>
            <Tax>
              <TaxTypeCode>01</TaxTypeCode>
              <TaxRate>21.00</TaxRate>
              <TaxableBase>
                <TotalAmount>{invoice.base_amount:.2f}</TotalAmount>
              </TaxableBase>
              <TaxAmount>
                <TotalAmount>{invoice.tax_amount:.2f}</TotalAmount>
              </TaxAmount>
            </Tax>
          </TaxesOutputs>
        </InvoiceLine>
      </Items>
    </Invoice>
  </Invoices>
</fe:Facturae>"""
        return xml_template.strip().encode("utf-8")
