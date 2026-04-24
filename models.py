from sqlalchemy import Column, Integer, String
from database import Base

class Training(Base):
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True)
    direction = Column(String)
    coaches = Column(String)
    place = Column(String)
    datetime = Column(String)
    max_slots = Column(Integer)
    price = Column(Integer)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    training_id = Column(Integer)
    user_id = Column(Integer)
    name = Column(String)