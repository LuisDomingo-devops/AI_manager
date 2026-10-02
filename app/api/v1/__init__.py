# API v1 Modular Routers
from fastapi import APIRouter
from .billing_router import router as billing_router
from .accounting_router import router as accounting_router
from .banking_router import router as banking_router
from .compliance_router import router as compliance_router
from .advisor_router import router as advisor_router
from .tasks_router import router as tasks_router
from .subscriptions_router import router as subscriptions_router
from .onboarding_router import router as onboarding_router
from .auth_router import router as auth_router
from .import_api import router as import_router
from .tax_models_router import router as tax_models_router
from .financial_statements_router import router as financial_statements_router
from .market_intelligence_router import router as market_intelligence_router
from .email_invoice_router import router as email_invoice_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router, tags=["Auth & Usuarios"])
api_v1_router.include_router(billing_router, tags=["Billing & E-Invoice"])
api_v1_router.include_router(accounting_router, tags=["Accounting PGC"])
api_v1_router.include_router(financial_statements_router, tags=["Financial Statements & Cierre Contable"])
api_v1_router.include_router(market_intelligence_router, tags=["Market Intelligence & DAFO"])
api_v1_router.include_router(banking_router, tags=["Open Banking PSD2"])
api_v1_router.include_router(compliance_router, tags=["Compliance Veri*Factu"])
api_v1_router.include_router(advisor_router, tags=["Advisor Portal"])
api_v1_router.include_router(tasks_router, tags=["Background Tasks"])
api_v1_router.include_router(subscriptions_router, tags=["Subscriptions & SaaS Licensing"])
api_v1_router.include_router(onboarding_router, tags=["Onboarding & Setup Wizard"])
api_v1_router.include_router(import_router, tags=["Import"])
api_v1_router.include_router(tax_models_router, tags=["Tax Models & BOE Filing"])
api_v1_router.include_router(email_invoice_router, tags=["Email Invoices & OCR"])
