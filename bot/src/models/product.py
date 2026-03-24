
from pydantic import BaseModel


class Product(BaseModel):
    category: str
    model: str
    description: str
    price: int
    photo_id: str
