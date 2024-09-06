from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Form
from sqlalchemy.orm import Session
from typing import List, Dict
from . import crud, models, schemas
from .database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
import os
import pandas as pd
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

local_network = "10.0.0."
origins=[
    "http://localhost",
    "http://localhost:3000",
    *[f"http://{local_network}{i}:3000" for i in range(1, 255)],
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def translate_headers(df):
    bank_headers = {
        'Chase': {
            'Transaction Date': 'Transaction_Date', 
            'Post Date': 'Post_Date', 
            'Description': 'Description',
            'Category': 'Category', 
            'Type': 'Budget', 
            'Amount': 'Amount', 
            'Memo': 'Memo'
        },
        'US Bank': {
            'Date': 'Transaction_Date',    
            'Transaction': 'Type', 
            'Name': 'Description', 
            'Memo': 'Memo', 
            'Amount': 'Amount'
        },
        'AMEX': {
            'Date': 'Transaction_Date',  
            'Description': 'Description',
            'Amount': 'Amount'
        },
        'Wells Fargo': {
            'Date': 'Transaction_Date',  
            'Description': 'Description',
            'Empty1': 'Empty1',
            'Empty2': 'Empty2',
            'Amount': 'Amount'
        }
    }

    for bank, headers in bank_headers.items():
        if set(headers.keys()).issubset(set(df.columns)):
            df = df.rename(columns=headers)

            if bank == 'AMEX':
                df['Amount'] = df['Amount'] * -1
                
            return df
    
    return None

@app.get("/")
async def root():
    return {"message": "CORS should be enabled"}

@app.post("/groups/", response_model=schemas.UserGroup)
def create_group(group: schemas.UserGroupCreate, db: Session = Depends(get_db)):
    db_group = crud.get_group_by_name(db, name=group.name)
    if db_group:
        raise HTTPException(status_code=400, detail="Group already registered")
    return crud.create_group(db=db, group=group)

@app.get("/groups/balances", response_model=List[schemas.GroupBalance])
def get_group_balances(db: Session = Depends(get_db)):
    # Fetch all groups
    groups = crud.get_groups(db)
    
    if not groups:
        raise HTTPException(status_code=404, detail="No groups found")
    
    group_balances = []
    
    # Iterate over each group to calculate balances
    for group in groups:
        balance_person1 = 0
        balance_person2 = 0

        # Get all files for the current group
        files = crud.get_files_by_group_id(db, group_id=group.id)

        # Sum the balances from the files
        for file in files:
            balance_person1 += file.balance_person1
            balance_person2 += file.balance_person2

        # Create a GroupBalance schema and add it to the list
        group_balance = schemas.GroupBalance(
            id=group.id,
            name=group.name, 
            person1=group.person1, 
            person2=group.person2,
            balance_person1=balance_person1, 
            balance_person2=balance_person2
        )
        group_balances.append(group_balance)

    # Return the list of group balances
    return group_balances

@app.get("/groups/{group_id}", response_model=schemas.UserGroup)
def read_group(group_id: int, db: Session = Depends(get_db)):
    db_group = crud.get_group(db, group_id=group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return db_group

@app.get("/groups/", response_model=List[schemas.UserGroup])
def read_groups(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    groups = db.query(models.UserGroup).filter(models.UserGroup.is_hidden == False).offset(skip).limit(limit).all()
    return groups

@app.get("/groups/{group_id}/files", response_model=List[schemas.File])
def read_files_for_group(group_id: int, db: Session = Depends(get_db)):
    db_group = crud.get_group(db, group_id=group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return crud.get_files_by_group_id(db, group_id=group_id)

@app.get("/files/{file_id}", response_model=schemas.File)
def read_file(file_id: int, db: Session = Depends(get_db)):
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file

@app.get("/files/{file_id}/transactions", response_model=List[schemas.Transaction])
def read_transactions_for_file(file_id: int, db: Session = Depends(get_db)):
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return crud.get_transactions_by_file_id(db, file_id=file_id)

@app.post("/files/{file_id}/transactions", response_model=List[schemas.Transaction])
def create_transactions_for_file(file_id: int, transactions: List[schemas.TransactionCreate], db: Session = Depends(get_db)):
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    db_transactions = [crud.create_transaction(db=db, transaction=transaction, file_id=file_id) for transaction in transactions]
    return db_transactions

@app.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def read_transaction(transaction_id: int, db: Session = Depends(get_db)):
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_transaction

@app.post("/groups/{group_id}/upload", response_model=schemas.File)
async def upload_file(group_id: int, 
                      owner: str = Form(...),  # Capture the owner from the form data
                      file: UploadFile = File(...), 
                      db: Session = Depends(get_db)):
    
    # Fetch the group from the database
    group = crud.get_group(db, group_id=group_id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Save file to disk or process it in-memory
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{group_id}_{file.filename}")

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Read the file to process transactions
    try:
        df = pd.read_csv(file_path)
        logger.debug(f"CSV DataFrame before translation: {df.head()}")
        df = translate_headers(df)
        if df is None:
            logger.error("Unsupported bank")
            raise HTTPException(status_code=400, detail="Unsupported bank")
        logger.debug(f"CSV DataFrame after translation: {df.head()}")
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    # Create a new file record in the database
    file_data = schemas.FileCreate(name=file.filename, group_id=group_id, owner=owner)
    db_file = crud.create_file(db=db, file=file_data)
    print('FILE ID: ', db_file.id)
    transactions = []  # Initialize the transactions list
    
    try:
        # Use the created file ID to associate transactions
        for index, row in df.iterrows():
            transaction = schemas.TransactionCreate(
                date=row['Transaction_Date'],
                description=row['Description'],
                amount=row['Amount'],
                action='Ignore',  # Use the correct field name
                file_id=db_file.id,  # Ensure file_id is included
                owner=owner,
                previous_action=''
            )
            transactions.append(crud.create_transaction(db=db, transaction=transaction))
    except Exception as e:
        logger.error(f"Error creating transactions: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error creating transactions: {str(e)}")
    
    return db_file


@app.post("/groups/{group_id}/transactions", response_model=List[schemas.Transaction])
async def save_transactions(group_id: int, transactions_data: List[schemas.TransactionCreate], db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id=group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    processed_transactions = []

    for transaction in transactions_data:
        # Use the new create_or_update_transaction function
        processed_transaction = crud.create_or_update_transaction(db=db, transaction=transaction)
        processed_transactions.append(processed_transaction)

    return processed_transactions

@app.post("/files/{file_id}/balances", response_model=schemas.File)
def update_file_balances(file_id: int, balances: schemas.FileBalanceUpdate, db: Session = Depends(get_db)):
    # Fetch the file by ID
    db_file = crud.get_file(db=db, file_id=file_id)
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update the balances
    db_file.balance_person1 = balances.balance_person1
    db_file.balance_person2 = balances.balance_person2
    
    # Commit the changes to the database
    db.commit()
    db.refresh(db_file)
    
    return db_file

@app.get("/groups/{group_id}/balance", response_model=schemas.GroupBalance)
def get_group_balance(group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id=group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    
    balance_person1 = 0
    balance_person2 = 0

    files = crud.get_files_by_group_id(db, group_id=group_id)
    for file in files:
        balance_person1 += file.balance_person1
        balance_person2 += file.balance_person2

    return schemas.GroupBalance(id=group_id, balance_person1=balance_person1, balance_person2=balance_person2)


@app.post("/transactions/query-actions")
async def query_past_actions(request: schemas.QueryActionsRequest, db: Session = Depends(get_db)):
    descriptions = request.descriptions
    owner = request.owner

    results = {}
    for description in descriptions:
        # Query the most recent action for this description
        transaction = (
            db.query(models.Transaction)
            .filter(models.Transaction.description == description)
            .filter(models.Transaction.owner == owner)
            .order_by(models.Transaction.date.desc())
            .first()
        )
        if transaction:
            results[description] = transaction.action
    return results

@app.delete("/groups/{group_id}/files/{file_id}")
def delete_file(group_id: int, file_id: int, db: Session = Depends(get_db)):
    # Find the file by ID
    file = db.query(models.File).filter(models.File.id == file_id, models.File.group_id == group_id).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete associated transactions
    db.query(models.Transaction).filter(models.Transaction.file_id == file.id).delete()

    # Delete the file
    db.delete(file)
    db.commit()

    return {"detail": "File and associated transactions deleted successfully"}

@app.put("/groups/{group_id}/hide")
async def hide_group(group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    else:
        group.is_hidden = True  # Set the flag to hide the group
        db.commit()
        # db.refresh(group)
    
        return {"message": "Group hidden successfully"}

@app.patch("/groups/{group_id}/archive")
async def archive_group(group_id: int, db: Session = Depends(get_db)):

    group = crud.get_group(db, group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.is_archived = True  # Set the flag to hide the group
    
    db.commit()
    # db.refresh(group)

    return {"message": "Group archived successfully"}

@app.patch("/groups/{group_id}/restore")
async def archive_group(group_id: int, db: Session = Depends(get_db)):

    # body = request.json()  # This reads and parses the body as JSON
    # print(f"Request Body: {body}") 

    group = crud.get_group(db, group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.is_archived = False  # Set the flag to hide the group
    
    db.commit()
    # db.refresh(group)

    return {"message": "Group restored successfully"}

@app.patch("/groups/{group_id}/settle")
async def settle_group(group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # files = crud.get_files_by_group_id(group_id)
    
    # group_balance_person1 = 0
    # group_balance_person2 = 0

    # for file in files:
    #     balance_person1 += file.balance_person1
    #     balance_person2 += file.balance_person2
    
    # settle_amount = group_balance_person1 - group_balance_person2
    
    # if settle_amount < 0:
        # the determine who owes who

    # settle_description = f"Settle Balance for Group {group.name}"

    # # Create a transaction to settle the balance
    # settle_transaction = models.Transaction(
    #     group_id=group.id,
    #     description=settle_description,
    #     amount=total_balance,
    #     transaction_type="settle"
    # )

    # will need to create a file to add the settled transaction

    # db.add(settle_transaction)
    
    group.is_settled = True
    db.commit()
    db.refresh(group)
    
    return {"message": "Group settled successfully", "group": group}

# Unsettle a Group
@app.patch("/groups/{group_id}/unsettle")
async def unsettle_group(group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.is_settled = False
    db.commit()
    db.refresh(group)
    
    return {"message": "Group unsettled successfully", "group": group}