from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base

class UserGroup(Base):
    __tablename__ = 'user_groups'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    person1 = Column(String)
    person2 = Column(String)
    is_hidden = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

    files = relationship('File', back_populates='group')

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    group_id = Column(Integer, ForeignKey('user_groups.id'))
    owner = Column(String)
    balance_person1 = Column(Float, default=0.0)
    balance_person2 = Column(Float, default=0.0)
    
    group = relationship("UserGroup", back_populates="files")
    transactions = relationship("Transaction", back_populates="file")


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String)
    description = Column(String)
    amount = Column(Integer)
    file_id = Column(Integer, ForeignKey('files.id'))
    action = Column(String)
    owner = Column(String)
    previous_action = Column(String, nullable=True)

    file = relationship('File', back_populates='transactions')
