from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    category_id: int
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    category_id: int | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    price: float
    stock: int
    image_url: str | None
    is_active: bool
    category: CategoryOut
    created_at: datetime


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    line_total: float


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: float


class Checkout(BaseModel):
    shipping_address: str = Field(min_length=10, max_length=500)
    coupon_code: str | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    unit_price: float
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    subtotal: float
    discount: float
    total: float
    shipping_address: str
    created_at: datetime
    items: list[OrderItemOut]


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=700)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    product_id: int
    rating: int
    comment: str
    created_at: datetime


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    discount_percent: float = Field(gt=0, le=80)

