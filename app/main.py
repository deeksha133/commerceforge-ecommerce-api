import os
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .database import Base, SessionLocal, engine, get_db
from .security import admin_user, create_token, current_user, hash_password, verify_password


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def seed_database() -> None:
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if admin_email and admin_password and not db.scalar(select(models.User).where(models.User.email == admin_email)):
            db.add(models.User(name=os.getenv("ADMIN_NAME", "Store Admin"), email=admin_email, password_hash=hash_password(admin_password), role="admin"))
        category_names = ["Electronics", "Lifestyle", "Home Office", "Wellness", "Travel"]
        categories = {}
        for name in category_names:
            slug = slugify(name)
            category = db.scalar(select(models.Category).where(models.Category.slug == slug))
            if not category:
                category = models.Category(name=name, slug=slug)
                db.add(category)
                db.flush()
            categories[slug] = category

        catalog = [
            ("Nebula Wireless Headphones", "Immersive over-ear headphones with active noise cancellation and 40-hour battery life.", 149.99, 25, "electronics"),
            ("Orbit Mechanical Keyboard", "Compact hot-swappable keyboard with tactile switches and customizable RGB lighting.", 89.00, 40, "electronics"),
            ("Arc Portable Speaker", "Pocket-sized waterproof speaker with spatial audio and a durable recycled shell.", 64.90, 32, "electronics"),
            ("Pulse Smart Lamp", "Adaptive desk lighting with touch controls, focus modes, and warm evening tones.", 78.50, 18, "electronics"),
            ("Terra Smart Bottle", "Insulated stainless steel bottle with hydration reminders and temperature display.", 39.50, 60, "lifestyle"),
            ("Form Everyday Backpack", "Weather-resistant modular backpack with a padded laptop sleeve and hidden travel pocket.", 84.00, 28, "lifestyle"),
            ("Frame Aluminum Stand", "Precision-machined adjustable laptop stand designed for an ergonomic workstation.", 54.75, 35, "home-office"),
            ("Drift Desk Mat", "Soft-touch recycled desk mat with a non-slip natural rubber base and stitched edges.", 32.00, 45, "home-office"),
            ("Focus Pomodoro Dial", "A tactile productivity timer with silent operation and a calming progress light.", 46.90, 20, "home-office"),
            ("Balance Massage Mini", "Compact percussion massager with four intensity settings and USB-C charging.", 69.95, 22, "wellness"),
            ("Breathe Sleep Light", "A bedside breathing guide with amber light, white noise, and screen-free controls.", 58.25, 16, "wellness"),
            ("Roam Travel Adapter", "Universal 65W GaN adapter with four ports and coverage across more than 150 countries.", 72.00, 30, "travel"),
            ("Nomad Packing Set", "Lightweight compression organizers made from ripstop fabric with clear label windows.", 44.50, 38, "travel"),
        ]
        for name, description, price, stock, category_slug in catalog:
            if not db.scalar(select(models.Product).where(models.Product.name == name)):
                db.add(models.Product(name=name, description=description, price=price, stock=stock, category_id=categories[category_slug].id))
        if not db.scalar(select(models.Coupon).where(models.Coupon.code == "WELCOME10")):
            db.add(models.Coupon(code="WELCOME10", discount_percent=10))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    seed_database()
    yield


app = FastAPI(
    title="CommerceForge API",
    version="1.0.0",
    description="A secure, production-style e-commerce REST API with JWT auth, catalog, cart, inventory, orders, reviews and coupons.",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    contact={"name": "CommerceForge API Team"},
    license_info={"name": "MIT"},
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def landing():
    return FileResponse("app/static/index.html")


@app.get("/store", include_in_schema=False)
def storefront():
    return FileResponse("app/static/store.html")


@app.get("/docs", include_in_schema=False)
def developer_console():
    return FileResponse("app/static/docs.html")


@app.get("/redoc", include_in_schema=False)
def api_reference():
    return FileResponse("app/static/reference.html")


@app.get("/status", include_in_schema=False)
def status_page():
    return FileResponse("app/static/status.html")


@app.get("/health", tags=["System"])
def health(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/status", status_code=303)
    return {"status": "healthy", "service": "commerceforge", "version": app.version}


@app.post("/api/auth/register", response_model=schemas.Token, status_code=201, tags=["Authentication"])
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    user = models.User(name=payload.name.strip(), email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    db.refresh(user)
    return schemas.Token(access_token=create_token(user), user=user)


@app.post("/api/auth/login", response_model=schemas.Token, tags=["Authentication"])
def login(payload: schemas.Login, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return schemas.Token(access_token=create_token(user), user=user)


@app.get("/api/auth/me", response_model=schemas.UserOut, tags=["Authentication"])
def me(user: models.User = Depends(current_user)):
    return user


@app.get("/api/categories", response_model=list[schemas.CategoryOut], tags=["Catalog"])
def categories(db: Session = Depends(get_db)):
    return db.scalars(select(models.Category).order_by(models.Category.name)).all()


@app.post("/api/categories", response_model=schemas.CategoryOut, status_code=201, tags=["Admin"])
def create_category(payload: schemas.CategoryCreate, _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    category = models.Category(name=payload.name.strip(), slug=slugify(payload.name))
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category already exists")
    db.refresh(category)
    return category


@app.get("/api/products", response_model=list[schemas.ProductOut], tags=["Catalog"])
def list_products(
    search: str | None = Query(None, max_length=100), category: str | None = None,
    min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
    in_stock: bool = False, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(models.Product).options(joinedload(models.Product.category)).where(models.Product.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(models.Product.name.ilike(pattern), models.Product.description.ilike(pattern)))
    if category:
        stmt = stmt.join(models.Category).where(models.Category.slug == category)
    if min_price is not None:
        stmt = stmt.where(models.Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(models.Product.price <= max_price)
    if in_stock:
        stmt = stmt.where(models.Product.stock > 0)
    return db.scalars(stmt.order_by(models.Product.created_at.desc()).offset(skip).limit(limit)).all()


@app.get("/api/products/{product_id}", response_model=schemas.ProductOut, tags=["Catalog"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.scalar(select(models.Product).options(joinedload(models.Product.category)).where(models.Product.id == product_id, models.Product.is_active.is_(True)))
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@app.post("/api/products", response_model=schemas.ProductOut, status_code=201, tags=["Admin"])
def create_product(payload: schemas.ProductCreate, _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    if not db.get(models.Category, payload.category_id):
        raise HTTPException(404, "Category not found")
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return get_product(product.id, db)


@app.patch("/api/products/{product_id}", response_model=schemas.ProductOut, tags=["Admin"])
def update_product(product_id: int, payload: schemas.ProductUpdate, _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    values = payload.model_dump(exclude_unset=True)
    if "category_id" in values and not db.get(models.Category, values["category_id"]):
        raise HTTPException(404, "Category not found")
    for key, value in values.items():
        setattr(product, key, value)
    db.commit()
    return get_product(product.id, db)


@app.delete("/api/products/{product_id}", status_code=204, tags=["Admin"])
def archive_product(product_id: int, _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    product.is_active = False
    db.commit()
    return Response(status_code=204)


def cart_response(user_id: int, db: Session) -> schemas.CartOut:
    rows = db.scalars(select(models.CartItem).options(joinedload(models.CartItem.product)).where(models.CartItem.user_id == user_id)).all()
    items = [schemas.CartItemOut(id=row.id, product_id=row.product_id, product_name=row.product.name, quantity=row.quantity, unit_price=row.product.price, line_total=round(row.quantity * row.product.price, 2)) for row in rows]
    return schemas.CartOut(items=items, total=round(sum(item.line_total for item in items), 2))


@app.get("/api/cart", response_model=schemas.CartOut, tags=["Cart"])
def get_cart(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return cart_response(user.id, db)


@app.post("/api/cart/items", response_model=schemas.CartOut, status_code=201, tags=["Cart"])
def add_cart_item(payload: schemas.CartItemCreate, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    product = db.get(models.Product, payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Product not found")
    if payload.quantity > product.stock:
        raise HTTPException(409, f"Only {product.stock} units are available")
    item = db.scalar(select(models.CartItem).where(models.CartItem.user_id == user.id, models.CartItem.product_id == product.id))
    if item:
        item.quantity = payload.quantity
    else:
        db.add(models.CartItem(user_id=user.id, product_id=product.id, quantity=payload.quantity))
    db.commit()
    return cart_response(user.id, db)


@app.delete("/api/cart/items/{product_id}", response_model=schemas.CartOut, tags=["Cart"])
def remove_cart_item(product_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(models.CartItem).where(models.CartItem.user_id == user.id, models.CartItem.product_id == product_id))
    if not item:
        raise HTTPException(404, "Cart item not found")
    db.delete(item)
    db.commit()
    return cart_response(user.id, db)


@app.post("/api/orders/checkout", response_model=schemas.OrderOut, status_code=201, tags=["Orders"])
def checkout(payload: schemas.Checkout, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    cart = db.scalars(select(models.CartItem).options(joinedload(models.CartItem.product)).where(models.CartItem.user_id == user.id)).all()
    if not cart:
        raise HTTPException(400, "Your cart is empty")
    for item in cart:
        if not item.product.is_active or item.quantity > item.product.stock:
            raise HTTPException(409, f"Insufficient stock for {item.product.name}")
    subtotal = round(sum(item.quantity * item.product.price for item in cart), 2)
    discount = 0.0
    if payload.coupon_code:
        coupon = db.scalar(select(models.Coupon).where(func.upper(models.Coupon.code) == payload.coupon_code.upper(), models.Coupon.is_active.is_(True)))
        if not coupon:
            raise HTTPException(400, "Invalid coupon code")
        discount = round(subtotal * coupon.discount_percent / 100, 2)
    order = models.Order(user_id=user.id, subtotal=subtotal, discount=discount, total=round(subtotal - discount, 2), shipping_address=payload.shipping_address)
    db.add(order)
    db.flush()
    for item in cart:
        item.product.stock -= item.quantity
        order.items.append(models.OrderItem(product_id=item.product_id, product_name=item.product.name, unit_price=item.product.price, quantity=item.quantity))
        db.delete(item)
    db.commit()
    db.refresh(order)
    return order


@app.get("/api/orders", response_model=list[schemas.OrderOut], tags=["Orders"])
def order_history(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.Order).options(joinedload(models.Order.items)).where(models.Order.user_id == user.id).order_by(models.Order.created_at.desc())).unique().all()


@app.get("/api/admin/orders", response_model=list[schemas.OrderOut], tags=["Admin"])
def all_orders(_: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.Order).options(joinedload(models.Order.items)).order_by(models.Order.created_at.desc())).unique().all()


@app.patch("/api/admin/orders/{order_id}/status", response_model=schemas.OrderOut, tags=["Admin"])
def update_order_status(order_id: int, order_status: str = Query(pattern="^(placed|paid|shipped|delivered|cancelled)$"), _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    order = db.scalar(select(models.Order).options(joinedload(models.Order.items)).where(models.Order.id == order_id))
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = order_status
    db.commit()
    return order


@app.get("/api/products/{product_id}/reviews", response_model=list[schemas.ReviewOut], tags=["Reviews"])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(models.Review).where(models.Review.product_id == product_id).order_by(models.Review.created_at.desc())).all()


@app.post("/api/products/{product_id}/reviews", response_model=schemas.ReviewOut, status_code=201, tags=["Reviews"])
def create_review(product_id: int, payload: schemas.ReviewCreate, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(models.Product, product_id):
        raise HTTPException(404, "Product not found")
    review = models.Review(user_id=user.id, product_id=product_id, **payload.model_dump())
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You have already reviewed this product")
    db.refresh(review)
    return review


@app.post("/api/admin/coupons", status_code=201, tags=["Admin"])
def create_coupon(payload: schemas.CouponCreate, _: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    coupon = models.Coupon(code=payload.code.upper(), discount_percent=payload.discount_percent)
    db.add(coupon)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Coupon already exists")
    return {"id": coupon.id, "code": coupon.code, "discount_percent": coupon.discount_percent}
