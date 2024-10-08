from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TransactionBase(BaseModel):
    date: str
    description: str
    amount: float
    action: str
    owner: str
    previous_action: str = None
    file_id: int

class QueryActionsRequest(BaseModel):
    descriptions: List[str]
    owner: str

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    file_id: int

    class Config:
        orm_mode = True

class FileBase(BaseModel):
    name: str
    group_id: int
    owner: str
    balance_person1: float = 0.0
    balance_person2: float = 0.0

class FileCreate(FileBase):
    pass

class File(FileBase):
    id: int

    class Config:
        orm_mode = True

class FileBalanceUpdate(BaseModel):
    balance_person1: float
    balance_person2: float

    class Config:
        orm_mode = True

class UserGroupBase(BaseModel):
    name: str
    person1: str
    person2: str
    is_hidden: Optional[bool] = False
    is_archived: Optional[bool] = False
    date_created: Optional[datetime] = None
    is_settled: Optional[bool] = False

    class Config:
        orm_mode = True

class UserGroupCreate(UserGroupBase):
    pass

class UserGroup(UserGroupBase):
    id: int
    files: List[File] = []

    class Config:
        orm_mode = True

class GroupBalance(UserGroupBase):
    id: int
    balance_person1: float
    balance_person2: float
    