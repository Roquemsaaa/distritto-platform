import pytest
from pydantic import ValidationError
from app.models import ProductCreate

def valid_product():
    return {
        "id": "dtt-ins-001",
        "brand": "DISTRITTO",
        "name": "Insignia",
        "collection_id": "raices",
        "reference": "DTT-INS-001",
        "price_cop": 60000,
        "product_folder": "DTT-INS-001",
        "description": "Prueba",
        "variants": [{
            "client_key": "v1",
            "id": "negro",
            "name": "Negro",
            "folder": "NEGRO",
            "image_count": 2
        }]
    }

def test_accepts_safe_folders():
    ProductCreate.model_validate(valid_product())

def test_rejects_path_traversal():
    data = valid_product()
    data["product_folder"] = "../secrets"
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(data)
