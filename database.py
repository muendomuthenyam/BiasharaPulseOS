# database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = f"sqlite:///./{os.getenv('SQLITE_DB_PATH', 'biashara.db')}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 30}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String, index=True)
    business_type = Column(String)  
    business_tier = Column(String, default="Tier 1: Micro / Kiosk")
    owner_name = Column(String)
    phone_number = Column(String)
    email = Column(String, index=True)
    
    # Dual Independent PIN Hashes for strict Role-Based Access Control (RBAC)
    owner_pin_hash = Column(String)
    attendant_pin_hash = Column(String)
    
    pin_salt = Column(String, nullable=True)
    subscription_status = Column(String, default="trialing") # trialing, active, expired
    trial_ends_at = Column(DateTime, nullable=True)
    device_fingerprint = Column(String, nullable=True) 
    license_key = Column(String, unique=True, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    business_type = Column(String)
    category = Column(String)
    unit_measure = Column(String)
    quantity = Column(Float)
    buying_price = Column(Float)
    selling_price = Column(Float)
    expiry_date = Column(String, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    receipt_code = Column(String, unique=True, index=True)
    total_amount = Column(Float)
    payment_method = Column(String)
    items_summary = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class CustomerCredit(Base):
    __tablename__ = "customer_credits"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    phone_number = Column(String)
    amount_owed = Column(Float)
    days_sales_outstanding = Column(Integer)
    risk_score = Column(String, default="Normal")
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="Pending")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String)
    amount = Column(Float)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class HotelRoom(Base):
    __tablename__ = "hotel_rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, unique=True)
    room_type = Column(String)
    price_per_night = Column(Float)
    status = Column(String, default="Available")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    performed_by = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)