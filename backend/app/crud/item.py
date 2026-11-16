"""Hàm thao tác database (CRUD) cho bảng items."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


def get_items(db: Session, keyword: str | None = None) -> list[Item]:
    stmt = select(Item)
    if keyword:
        stmt = stmt.where(Item.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(Item.id.desc())
    return list(db.scalars(stmt).all())


def get_item(db: Session, item_id: int) -> Item | None:
    return db.get(Item, item_id)


def create_item(db: Session, data: ItemCreate) -> Item:
    item = Item(
        name=data.name,
        description=data.description,
        price=data.price,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: Item, data: ItemUpdate) -> Item:
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: Item) -> None:
    db.delete(item)
    db.commit()

