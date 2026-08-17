# API v1 Modular Routers
from fastapi import APIRouter
from .billing_router import router as billing_router
from .accounting_router import router as accounting_router
from .banking_router import router as banking_router
from .compliance_router import router as compliance_router
from .advisor_router import router as advisor_router
from .tasks_router import router as tasks_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(billing_router, tags=["Billing & E-Invoice"])
api_v1_router.include_router(accounting_router, tags=["Accounting PGC"])
api_v1_router.include_router(banking_router, tags=["Open Banking PSD2"])
api_v1_router.include_router(compliance_router, tags=["Compliance Veri*Factu"])
api_v1_router.include_router(advisor_router, tags=["Advisor Portal"])
api_v1_router.include_router(tasks_router, tags=["Background Tasks"])
