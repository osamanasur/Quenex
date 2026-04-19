from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='attendee')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    events = db.relationship('Event', backref='organizer', lazy=True)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)
    support_tickets = db.relationship('SupportTicket', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200), default='default-event.jpg')
    event_fee = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    is_paid = db.Column(db.Boolean, default=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ticket_types = db.relationship('TicketType', backref='event', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='event', lazy=True)

class TicketType(db.Model):
    __tablename__ = 'ticket_types'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    quantity_available = db.Column(db.Integer, nullable=False)
    
    def tickets_remaining(self):
        from database import Booking
        sold = sum(b.quantity for b in Booking.query.filter_by(event_id=self.event_id, ticket_type=self.name, status='confirmed').all())
        return self.quantity_available - sold

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticket_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    attendee_name = db.Column(db.String(100), nullable=False)
    attendee_email = db.Column(db.String(120), nullable=False)
    attendee_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    checked_in = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payment = db.relationship('Payment', backref='booking', uselist=False, cascade='all, delete-orphan')

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), nullable=False, default='mobile_money')
    transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_type = db.Column(db.String(20), default='ticket')  # ticket, event_fee
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')
    admin_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    """Initialize the database with tables and default admin user"""
    db.create_all()
    
    # Create default admin user if not exists
    admin = User.query.filter_by(email='admin@quenex.com').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@quenex.com',
            phone='+256769271812',
            role='admin',
            status='active'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: admin@quenex.com / admin123")
    
    # Create demo organizer
    demo_org = User.query.filter_by(email='organizer@quenex.com').first()
    if not demo_org:
        demo_org = User(
            username='demo_organizer',
            email='organizer@quenex.com',
            phone='+256769271813',
            role='organizer',
            status='active'
        )
        demo_org.set_password('organizer123')
        db.session.add(demo_org)
        db.session.commit()
        print("Demo organizer created: organizer@quenex.com / organizer123")
    
    # Create demo attendee
    demo_attendee = User.query.filter_by(email='attendee@quenex.com').first()
    if not demo_attendee:
        demo_attendee = User(
            username='demo_attendee',
            email='attendee@quenex.com',
            phone='+256769271814',
            role='attendee',
            status='active'
        )
        demo_attendee.set_password('attendee123')
        db.session.add(demo_attendee)
        db.session.commit()
        print("Demo attendee created: attendee@quenex.com / attendee123")
    
    print("Database initialized successfully!")