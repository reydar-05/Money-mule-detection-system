from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
from io import BytesIO
from fastapi.responses import StreamingResponse
import matplotlib.dates as mdates

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root:Renu123@localhost/moneytable")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# ✅ Fixed Transactions Table
class Transaction(Base):
    __tablename__ = "transactions"
    Profile_ID = Column(Integer, primary_key=True, index=True)
    Source_Account = Column(Integer, nullable=False)
    Destination_Account = Column(Integer, nullable=False)
    Amount = Column(Float, nullable=False)
    Date = Column(DateTime, nullable=False)
    Time = Column(DateTime, default=datetime.utcnow)
    Transaction_Type = Column(String(15), nullable=False)
    Source_Bank = Column(String(15), nullable=False)
    Destination_Bank = Column(String(15), nullable=False)
    Source_Branch = Column(String(15), nullable=False)
    Destination_Branch = Column(String(15), nullable=False)
    Place_of_Transaction = Column(String(15), nullable=False)
    Transaction_Device = Column(String(15), nullable=False)
    Transaction_Currency = Column(String(10), nullable=False)
    Transaction_Country = Column(String(50), nullable=False)
    Transaction_Limit = Column(Float, nullable=False)
    IP_Address = Column(String(20), nullable=False)
    Risk_Categories = Column(String(20), nullable=False)
    Flagged = Column(Boolean, default=False)  # ✅ Added a Flagged column

Base.metadata.create_all(bind=engine)

# ✅ Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Fixed Transaction Creation Endpoint
@app.post("/transactions/")
def create_transaction(
    profile_id: int, amount: float, currency: str, country: str, db: Session = Depends(get_db)
):
    flagged = check_aml_rules(profile_id, amount, currency, country, db)

    transaction = Transaction(
        Profile_ID=profile_id,
        Amount=amount,
        Transaction_Currency=currency,
        Transaction_Country=country,
        Flagged=flagged,
        Date=datetime.utcnow(),
        Time=datetime.utcnow()
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {"transaction_id": transaction.Profile_ID, "flagged": transaction.Flagged}

# ✅ Fixed AML Rule Checking
def check_aml_rules(profile_id: int, amount: float, currency: str, country: str, db: Session) -> bool:
    high_risk_countries = {"North Korea", "Iran", "Syria", "Sudan", "Romania", "Nigeria", "Ghana", "Ukraine"}
    threshold = 10000
    rapid_transaction_limit = 3
    suspicious_currencies = {"BTC", "XMR"}
    structured_transaction_limit = 900000
    unusual_hour_start, unusual_hour_end = 23, 5

    if country in high_risk_countries:
        return True

    recent_transactions = db.query(Transaction).filter(Transaction.Profile_ID == profile_id).count()
    if recent_transactions > 5:
        return True

    if amount > threshold:
        return True

    recent_timeframe = datetime.utcnow() - timedelta(minutes=5)
    rapid_transactions = db.query(Transaction).filter(
        Transaction.Profile_ID == profile_id,
        Transaction.Time >= recent_timeframe
    ).count()
    if rapid_transactions > rapid_transaction_limit:
        return True

    if currency in suspicious_currencies:
        return True

    recent_structured_transactions = db.query(Transaction).filter(
        Transaction.Profile_ID == profile_id,
        Transaction.Amount < structured_transaction_limit
    ).count()
    if recent_structured_transactions > 5:
        return True

    current_hour = datetime.utcnow().hour
    if unusual_hour_start <= current_hour or current_hour < unusual_hour_end:
        return True

    return False

# ✅ Fixed Visualization Endpoint
@app.get("/transactions/visualization", tags=["Visualization"])
async def get_flagged_transactions_visualization(db: Session = Depends(get_db)):
    flagged_transactions = db.query(Transaction).filter(Transaction.Flagged == True).all()
    
    if not flagged_transactions:
        return {"message": "No flagged transactions found"}

    dates = [txn.Time.date() for txn in flagged_transactions]
    date_counts = {}

    for date in dates:
        date_counts[date] = date_counts.get(date, 0) + 1

    sorted_dates = sorted(date_counts.keys())
    counts = [date_counts[date] for date in sorted_dates]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(sorted_dates, counts, marker='o', linestyle='-', color='r')
    ax.set_title('Flagged Transactions Over Time')
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Flagged Transactions')

    plt.xticks(rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)

    return StreamingResponse(img, media_type="image/png")
