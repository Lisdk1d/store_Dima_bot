
from pydantic import BaseModel


class Product(BaseModel):
    category: str
    model: str
    description: str
    price: str
    photo_id: str
