from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base,sessionmaker, Session
from datetime import datetime, timedelta
import os
import joblib
import numpy as np

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root:Renu123@localhost/moneytable")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

class Transaction(Base):
    __tablename__ = "transactions"
    Profile_ID = Column(Integer, primary_key=True, index=True)
    Source_Account= Column(Integer,nullable=False)
    Destination_Account=Column(Integer,nullable=False)
    Amount = Column(Float, nullable=False)
    Date=Column(DateTime,nullable=False)
    Time = Column(DateTime, default=datetime.utcnow)
    Transaction_Type=Column(String(15),nullable=False)
    Source_Bank=Column(String(15),nullable=False)
    Destination_Bank=Column(String(15),nullable=False)
    Source_Branch=Column(String(15),nullable=False)
    Destination_Branch=Column(String(15),nullable=False)
    Place_of_Transaction=Column(String(15),nullable=False)
    Transaction_Device=Column(String(15),nullable=False)
    Transaction_Currency = Column(String(10), nullable=False)
    Transaction_Country = Column(String(50), nullable=False)
    Transaction_Limit=Column(Float, nullable=False)
    IP_Address=Column(String(20), nullable=False)
    Risk_Categories=Column(String(20), nullable=False)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/transactions/")
def create_transaction(user_id: int, amount: float, currency: str, country: str, db: Session = Depends(get_db)):
    flagged_by_rules = check_aml_rules(user_id, amount, currency, country, db)
    flagged = flagged_by_rules
    
    transaction = Transaction(user_id=user_id, amount=amount, currency=currency, country=country, flagged=flagged)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {"transaction_id": transaction.id, "flagged": transaction.flagged}

def check_aml_rules(user_id: int, amount: float, currency: str, country: str, db: Session) -> bool:
    high_risk_countries = {"North Korea", "Iran", "Syria", "Sudan","Romania","Nigeria","Ghana","Ukraine"}
    threshold = 10000
    rapid_transaction_limit = 3  # More than 3 transactions in 5 minutes
    suspicious_currencies = {"BTC", "XMR"}  # Cryptocurrencies
    structured_transaction_limit = 900000  # Repeated transactions below reporting limit
    unusual_hour_start, unusual_hour_end = 23, 5  # Unusual hours for transactions
    
    if country in high_risk_countries:
        return True
    
    recent_transactions = db.query(Transaction).filter(Transaction.user_id == user_id).count()
    if recent_transactions > 5:
        return True
    
    if amount > threshold:
        return True
    
    recent_timeframe = datetime.utcnow() - timedelta(minutes=5)
    rapid_transactions = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.timestamp >= recent_timeframe).count()
    if rapid_transactions > rapid_transaction_limit:
        return True
    
    if currency in suspicious_currencies:
        return True
    
    recent_structured_transactions = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.amount < structured_transaction_limit).count()
    if recent_structured_transactions > 5:
        return True
    
    current_hour = datetime.utcnow().hour
    if unusual_hour_start <= current_hour or current_hour < unusual_hour_end:
        return True
    
import matplotlib.pyplot as plt
from io import BytesIO
from fastapi.responses import StreamingResponse
import numpy as np
import matplotlib.dates as mdates

# Endpoint to visualize flagged transactions over time
@app.get("/transactions/visualization", tags=["Visualization"])
async def get_flagged_transactions_visualization(db: Session = Depends(get_db)):
    # Fetch the flagged transactions from the database
    flagged_transactions = db.query(Transaction).filter(Transaction.flagged == True).all()
    
    # Collect data for plotting
    dates = [txn.Time for txn in flagged_transactions]
    date_counts = {}
    
    for date in dates:
        date_str = date.date()  # Consider only the date (no time part)
        if date_str not in date_counts:
            date_counts[date_str] = 1
        else:
            date_counts[date_str] += 1
    
    # Prepare data for plotting
    sorted_dates = sorted(date_counts.keys())
    counts = [date_counts[date] for date in sorted_dates]
    
    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(sorted_dates, counts, marker='o', linestyle='-', color='r')
    ax.set_title('Flagged Transactions Over Time')
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Flagged Transactions')
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.tight_layout()

    # Save plot to a BytesIO object
    img = BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    
    # Return the image as a response
    return StreamingResponse(img, media_type="image/png")