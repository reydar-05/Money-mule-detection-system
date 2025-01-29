from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
import joblib
import numpy as np

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://user:password@localhost/aml_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

model = joblib.load("random_forest_model.pkl")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    country = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    flagged = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/transactions/")
def create_transaction(user_id: int, amount: float, currency: str, country: str, db: Session = Depends(get_db)):
    flagged_by_rules = check_aml_rules(user_id, amount, country, db)
    flagged_by_ai = check_aml_with_ai(user_id, amount, country, db)
    flagged = flagged_by_rules or flagged_by_ai
    
    transaction = Transaction(user_id=user_id, amount=amount, currency=currency, country=country, flagged=flagged)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {"transaction_id": transaction.id, "flagged": transaction.flagged}

def check_aml_rules(user_id: int, amount: float, country: str, db: Session) -> bool:
    high_risk_countries = {"North Korea", "Iran", "Syria", "Sudan"}
    threshold = 10000
    
    if country in high_risk_countries:
        return True
    
    recent_transactions = db.query(Transaction).filter(Transaction.user_id == user_id).count()
    if recent_transactions > 5:
        return True
    
    if amount > threshold:
        return True
    
    return False

def check_aml_with_ai(user_id: int, amount: float, country: str, db: Session) -> bool:
    recent_transactions = db.query(Transaction).filter(Transaction.user_id == user_id).count()
    input_features = np.array([[user_id, amount, recent_transactions]]).astype(float)
    prediction = model.predict(input_features)
    return bool(prediction[0])