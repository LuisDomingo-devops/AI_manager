from app.config import settings
from app.domain.ports.tax_territory_port import TaxTerritoryPort
from app.infrastructure.tax_territories.common_territory import CommonTerritoryAdapter
from app.infrastructure.tax_territories.canarias_territory import CanariasTerritoryAdapter
from app.infrastructure.tax_territories.navarra_territory import NavarraTerritoryAdapter
from app.infrastructure.tax_territories.pais_vasco_territory import PaisVascoTerritoryAdapter

class TaxTerritoryFactory:
    _cached_adapters = {}

    @classmethod
    def get_current_territory(cls) -> TaxTerritoryPort:
        """
        Retorna el adaptador territorial activo según la configuración global settings.FISCAL_TERRITORY.
        """
        territory = getattr(settings, "FISCAL_TERRITORY", "comun").lower().strip()

        if territory not in cls._cached_adapters:
            if territory == "canarias":
                cls._cached_adapters[territory] = CanariasTerritoryAdapter()
            elif territory == "navarra":
                cls._cached_adapters[territory] = NavarraTerritoryAdapter()
            elif territory == "pais_vasco":
                cls._cached_adapters[territory] = PaisVascoTerritoryAdapter()
            else:
                cls._cached_adapters[territory] = CommonTerritoryAdapter()

        return cls._cached_adapters[territory]
