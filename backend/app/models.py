from pydantic import BaseModel, Field
from typing import Any

class CollectionIn(BaseModel): id:str; name:str
class CollectionUpdate(BaseModel): name:str
class VariantUpdate(BaseModel): id:str; name:str; color_hex:str='#111111'; folder:str=''; sku:str=''; unit_cost_cop:int=Field(default=0,ge=0); active:bool=True
class ProductUpdate(BaseModel):
    brand:str; name:str; collection_id:str; reference:str; price_cop:int=Field(ge=0); description:str=''; tags:list[str]=[]; closure:str=''; type:str=''; active:bool=True; variants:list[VariantUpdate]=[]
class InventorySet(BaseModel): product_id:str; variant_id:str; stock:int=Field(ge=0); note:str='Ajuste manual'
class DiscountIn(BaseModel): id:str; name:str; discount_type:str; value:int=Field(gt=0); scope:str; target_id:str=''; active:bool=True; starts_at:str|None=None; ends_at:str|None=None
class EventIn(BaseModel):
    event_type:str; occurred_at:str|None=None; visitor_id:str=''; session_id:str=''; product_id:str=''; variant_id:str=''; collection_id:str=''; source:str=''; medium:str=''; campaign:str=''; referrer:str=''; device:str=''; page:str=''; numeric_value:float=0; metadata:dict[str,Any]={}
class SaleItemIn(BaseModel): product_id:str; variant_id:str; quantity:int=Field(gt=0); unit_price_cop:int=Field(ge=0)
class SaleIn(BaseModel): sold_at:str|None=None; channel:str='Manual'; customer_name:str=''; customer_contact:str=''; notes:str=''; discount_cop:int=Field(default=0,ge=0); items:list[SaleItemIn]
class ProductionInputIn(BaseModel): material_name:str; unit:str='unidad'; quantity:float=Field(ge=0); unit_cost_cop:float=Field(ge=0)
class ProductionIn(BaseModel): produced_at:str|None=None; product_id:str; variant_id:str; units_planned:int=Field(ge=0); units_produced:int=Field(gt=0); waste_units:int=Field(default=0,ge=0); labor_cost_cop:int=Field(default=0,ge=0); other_cost_cop:int=Field(default=0,ge=0); notes:str=''; inputs:list[ProductionInputIn]=[]
class SettingsIn(BaseModel): few_units_max:int=Field(default=2,ge=2); analytics_enabled:bool=True; cache_seconds:int=Field(default=60,ge=0,le=3600)
