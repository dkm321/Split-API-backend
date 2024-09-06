from sqlalchemy.orm import Session
from . import models, schemas
from typing import List

def get_file(db: Session, file_id: int):
    return db.query(models.File).filter(models.File.id == file_id).first()


def get_files_by_group_id(db: Session, group_id: int):
    return db.query(models.File).filter(models.File.group_id == group_id).all()

def get_transactions_by_file_id(db: Session, file_id: int):
    return db.query(models.Transaction).filter(models.Transaction.file_id == file_id).all()


def create_file(db: Session, file: schemas.FileCreate):
    db_file = models.File(
        name=file.name,
        group_id=file.group_id,
        owner=file.owner  # Save the owner field
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_group_by_name(db: Session, name: str):
    return db.query(models.UserGroup).filter(models.UserGroup.name == name).first()

def create_group(db: Session, group: schemas.UserGroupCreate):
    db_group = models.UserGroup(name=group.name, person1=group.person1, person2=group.person2)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_group(db: Session, group_id: int):
    return db.query(models.UserGroup).filter(models.UserGroup.id == group_id).first()

def get_groups(db: Session):
    return db.query(models.UserGroup).all()

def create_transaction(db: Session, transaction: schemas.TransactionCreate):
    db_transaction = models.Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def create_or_update_transaction(db: Session, transaction: schemas.TransactionCreate):
    # Check if the transaction already exists by unique attributes
    existing_transaction = db.query(models.Transaction).filter(
        models.Transaction.file_id == transaction.file_id,
        models.Transaction.date == transaction.date,
        models.Transaction.description == transaction.description,
        models.Transaction.amount == transaction.amount
    ).first()

    if existing_transaction:
        # Update the existing transaction
        existing_transaction.action = transaction.action
        existing_transaction.previous_action = transaction.previous_action
        existing_transaction.owner = transaction.owner
        db.commit()
        db.refresh(existing_transaction)
        return existing_transaction
    else:
        # Create a new transaction if it doesn't exist
        db_transaction = models.Transaction(**transaction.dict())
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return db_transaction
