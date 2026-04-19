from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db, User, Event, TicketType, Booking, Payment, AuditLog, SupportTicket, init_db
from werkzeug.utils import secure_filename
from datetime import datetime, date as today_date
from functools import wraps
import os
import qrcode
from io import BytesIO
import base64
import hashlib
import secrets
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Database configuration - No external dependencies needed
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # For PostgreSQL on Render (convert postgres:// to postgresql:// if needed)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Local development - Use SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quenex.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Rest of your app.py remains the same...

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    init_db()

# Event categories (prices removed for public view)
EVENT_CATEGORIES = {
    'social': {'name': 'Social Events', 'icon': 'fa-heart', 'description': 'Weddings, Birthdays, Reunions, Anniversaries'},
    'corporate': {'name': 'Corporate Events', 'icon': 'fa-briefcase', 'description': 'Conferences, Seminars, Trade Fairs'},
    'entertainment': {'name': 'Entertainment', 'icon': 'fa-music', 'description': 'Concerts, Festivals, Carnivals'},
    'sports': {'name': 'Sports & Fitness', 'icon': 'fa-futbol', 'description': 'Matches, Tournaments, Athletics'},
    'charity': {'name': 'Charity & Community', 'icon': 'fa-hand-holding-heart', 'description': 'Fundraisers, Outreaches, Galas'},
    'educational': {'name': 'Educational', 'icon': 'fa-graduation-cap', 'description': 'Lectures, Panels, Workshops'}
}

# Category prices for organizers (internal use only)
CATEGORY_PRICES = {
    'social': 0,
    'corporate': 200000,
    'entertainment': 200000,
    'sports': 150000,
    'charity': 0,
    'educational': 0
}

TICKET_TYPES = ['Ordinary', 'VIP', 'VVIP', 'Tables']

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def organizer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['organizer', 'admin']:
            flash('Access denied. Organizer privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def log_audit(action, user_id, details):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    today = today_date.today()
    upcoming_events = Event.query.filter(
        Event.date >= today, 
        Event.status == 'approved',
        Event.is_paid == True
    ).order_by(Event.date).limit(6).all()
    
    featured_events = Event.query.filter_by(
        status='approved', 
        is_paid=True
    ).order_by(Event.created_at.desc()).limit(3).all()
    
    return render_template('index.html', 
                         events=upcoming_events, 
                         featured=featured_events, 
                         categories=EVENT_CATEGORIES, 
                         today=today)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/events')
def events():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    date_filter = request.args.get('date', '')
    today = today_date.today()
    
    query = Event.query.filter(Event.date >= today, Event.status == 'approved', Event.is_paid == True)
    
    if category and category in EVENT_CATEGORIES:
        query = query.filter(Event.category == category)
    
    if search:
        query = query.filter(
            Event.title.contains(search) | 
            Event.description.contains(search) | 
            Event.venue.contains(search)
        )
    
    if date_filter:
        query = query.filter(Event.date == datetime.strptime(date_filter, '%Y-%m-%d').date())
    
    events_list = query.order_by(Event.date).all()
    return render_template('events.html', 
                         events=events_list, 
                         categories=EVENT_CATEGORIES, 
                         selected_category=category, 
                         search=search)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    if event.status != 'approved' or not event.is_paid:
        flash('This event is not available.', 'warning')
        return redirect(url_for('events'))
    
    ticket_types = TicketType.query.filter_by(event_id=event_id).all()
    today = today_date.today()
    return render_template('event_detail.html', 
                         event=event, 
                         ticket_types=ticket_types, 
                         categories=EVENT_CATEGORIES, 
                         today=today)

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/help')
def help_page():
    return render_template('help.html')

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        phone = request.form['phone']
        role = request.form['role']
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email, phone=phone, role=role)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if user.status != 'active':
                flash('Your account has been suspended. Contact admin.', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'organizer':
                return redirect(url_for('organizer_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ==================== ORGANIZER ROUTES ====================

@app.route('/organizer/dashboard')
@organizer_required
def organizer_dashboard():
    events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).all()
    total_events = len(events)
    total_bookings = Booking.query.join(Event).filter(Event.organizer_id == current_user.id, Booking.status == 'confirmed').count()
    
    total_revenue = db.session.query(db.func.sum(Payment.amount)).join(Booking).join(Event).filter(
        Event.organizer_id == current_user.id, Payment.status == 'completed'
    ).scalar() or 0
    
    pending_payment = Event.query.filter_by(organizer_id=current_user.id, is_paid=False, status='pending').count()
    
    return render_template('dashboard/organizer_dashboard.html', 
                         events=events, 
                         total_events=total_events,
                         total_bookings=total_bookings,
                         total_revenue=total_revenue,
                         pending_payment=pending_payment)

@app.route('/organizer/my-events')
@organizer_required
def organizer_my_events():
    events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).all()
    return render_template('dashboard/my_events.html', events=events, categories=EVENT_CATEGORIES)

@app.route('/organizer/create-event', methods=['GET', 'POST'])
@organizer_required
def create_event():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        venue = request.form['venue']
        event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d')
        event_time = request.form['event_time']
        capacity = int(request.form['capacity'])
        
        event_fee = CATEGORY_PRICES.get(category, 0)
        
        image_filename = 'default-event.jpg'
        if 'event_image' in request.files:
            file = request.files['event_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        new_event = Event(
            title=title,
            description=description,
            category=category,
            venue=venue,
            date=event_date,
            time=event_time,
            capacity=capacity,
            image=image_filename,
            event_fee=event_fee,
            organizer_id=current_user.id,
            status='pending',
            is_paid=False
        )
        
        db.session.add(new_event)
        db.session.commit()
        
        for ticket_type in TICKET_TYPES:
            new_ticket = TicketType(
                event_id=new_event.id,
                name=ticket_type,
                price=0,
                quantity_available=capacity
            )
            db.session.add(new_ticket)
        
        db.session.commit()
        
        if event_fee > 0:
            flash(f'Event created! Please pay UGX {event_fee:,.0f} to publish your event.', 'warning')
            return redirect(url_for('pay_event_fee', event_id=new_event.id))
        else:
            new_event.status = 'approved'
            new_event.is_paid = True
            db.session.commit()
            flash('Event created and published successfully! (Free category)', 'success')
        
        return redirect(url_for('organizer_dashboard'))
    
    return render_template('dashboard/create_event.html', categories=EVENT_CATEGORIES, category_prices=CATEGORY_PRICES)

# Update the pay_event_fee route - Fix the flash message
@app.route('/organizer/pay-event-fee/<int:event_id>', methods=['GET', 'POST'])
@organizer_required
def pay_event_fee(event_id):
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organizer_dashboard'))
    
    if request.method == 'POST':
        mobile_money_number = request.form.get('mobile_money_number')
        
        transaction_id = f"DEMO_FEE_{datetime.now().strftime('%Y%m%d%H%M%S')}_{event.id}"
        
        payment = Payment(
            booking_id=None,
            amount=event.event_fee,
            method='mobile_money_demo',
            transaction_id=transaction_id,
            status='completed',
            payment_type='event_fee'
        )
        db.session.add(payment)
        
        event.is_paid = True
        event.status = 'approved'
        db.session.commit()
        
        # Fixed: Use f-string with manual formatting
        flash(f'[DEMONSTRATION] Payment of UGX {event.event_fee:,.0f} simulated! Your event "{event.title}" is now published. In production, real money would be deducted from {mobile_money_number}', 'success')
        return redirect(url_for('organizer_dashboard'))
    
    return render_template('dashboard/pay_event_fee.html', event=event, categories=EVENT_CATEGORIES)

@app.route('/organizer/event/<int:event_id>/edit', methods=['GET', 'POST'])
@organizer_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organizer_dashboard'))
    
    if request.method == 'POST':
        event.title = request.form['title']
        event.description = request.form['description']
        event.venue = request.form['venue']
        event.date = datetime.strptime(request.form['event_date'], '%Y-%m-%d').date()
        event.time = request.form['event_time']
        event.capacity = int(request.form['capacity'])
        event.status = 'pending'
        event.is_paid = False
        
        if 'event_image' in request.files:
            file = request.files['event_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                event.image = filename
        
        db.session.commit()
        
        if event.event_fee > 0:
            flash('Event updated! Payment required to republish.', 'warning')
            return redirect(url_for('pay_event_fee', event_id=event.id))
        else:
            event.status = 'approved'
            event.is_paid = True
            db.session.commit()
            flash('Event updated successfully!', 'success')
        
        return redirect(url_for('organizer_my_events'))
    
    return render_template('dashboard/edit_event.html', event=event, categories=EVENT_CATEGORIES)

@app.route('/organizer/event/<int:event_id>/tickets', methods=['GET', 'POST'])
@organizer_required
def manage_tickets(event_id):
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organizer_dashboard'))
    
    if request.method == 'POST':
        ticket_ids = request.form.getlist('ticket_id')
        prices = request.form.getlist('price')
        quantities = request.form.getlist('quantity')
        
        for i, ticket_id in enumerate(ticket_ids):
            ticket = TicketType.query.get(ticket_id)
            if ticket:
                ticket.price = float(prices[i])
                ticket.quantity_available = int(quantities[i])
        
        db.session.commit()
        flash('Ticket pricing updated successfully!', 'success')
    
    ticket_types = TicketType.query.filter_by(event_id=event_id).all()
    return render_template('dashboard/manage_tickets.html', event=event, ticket_types=ticket_types)

@app.route('/organizer/event/<int:event_id>/analytics')
@organizer_required
def event_analytics(event_id):
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organizer_dashboard'))
    
    bookings = Booking.query.filter_by(event_id=event_id, status='confirmed').all()
    total_tickets_sold = sum(b.quantity for b in bookings)
    
    payments = Payment.query.join(Booking).filter(Booking.event_id == event_id, Payment.status == 'completed').all()
    total_revenue = sum(p.amount for p in payments)
    
    ticket_distribution = {}
    for ticket in TicketType.query.filter_by(event_id=event_id).all():
        sold = sum(b.quantity for b in bookings if b.ticket_type == ticket.name)
        ticket_distribution[ticket.name] = {'sold': sold, 'total': ticket.quantity_available}
    
    attendees = []
    for booking in bookings:
        attendees.append({
            'name': booking.attendee_name,
            'email': booking.attendee_email,
            'phone': booking.attendee_phone,
            'ticket_type': booking.ticket_type,
            'quantity': booking.quantity,
            'booking_date': booking.created_at,
            'checked_in': booking.checked_in
        })
    
    return render_template('dashboard/event_analytics.html', 
                         event=event, 
                         total_tickets_sold=total_tickets_sold,
                         total_revenue=total_revenue,
                         ticket_distribution=ticket_distribution,
                         attendees=attendees)

# ==================== ATTENDEE ROUTES ====================

# Update the checkout route - Fix the flash message
@app.route('/checkout/<int:event_id>', methods=['GET', 'POST'])
@login_required
def checkout(event_id):
    event = Event.query.get_or_404(event_id)
    
    if event.status != 'approved' or not event.is_paid:
        flash('This event is not available for booking.', 'danger')
        return redirect(url_for('events'))
    
    ticket_types = TicketType.query.filter_by(event_id=event_id).all()
    
    if request.method == 'POST':
        ticket_type = request.form.get('ticket_type')
        quantity = int(request.form.get('quantity', 1))
        attendee_name = request.form.get('attendee_name')
        attendee_phone = request.form.get('attendee_phone')
        mobile_money_number = request.form.get('mobile_money_number')
        
        ticket = TicketType.query.filter_by(event_id=event_id, name=ticket_type).first()
        if not ticket:
            flash('Invalid ticket type.', 'danger')
            return redirect(url_for('event_detail', event_id=event_id))
        
        total_amount = ticket.price * quantity
        
        # Check availability
        sold_count = sum(b.quantity for b in Booking.query.filter_by(event_id=event_id, ticket_type=ticket_type, status='confirmed').all())
        if sold_count + quantity > ticket.quantity_available:
            flash('Not enough tickets available.', 'danger')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Create booking
        booking = Booking(
            event_id=event_id,
            user_id=current_user.id,
            ticket_type=ticket_type,
            quantity=quantity,
            total_amount=total_amount,
            attendee_name=attendee_name,
            attendee_email=current_user.email,
            attendee_phone=attendee_phone,
            status='confirmed'
        )
        
        db.session.add(booking)
        db.session.commit()
        
        # DEMONSTRATION MODE - No real payment
        transaction_id = f"DEMO_TKT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{booking.id}"
        payment = Payment(
            booking_id=booking.id,
            amount=total_amount,
            method='mobile_money_demo',
            transaction_id=transaction_id,
            status='completed',
            payment_type='ticket'
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # Generate QR code
        qr_data = f"TICKET:{booking.id}:{event.title}:{attendee_name}:{ticket_type}:{quantity}"
        booking.qr_code = generate_qr_code(qr_data)
        
        # Fixed: Use f-string with manual formatting instead of format_currency
        flash(f'[DEMONSTRATION] Booking successful! Amount: UGX {total_amount:,.0f} simulated. In production, real money would be deducted from {mobile_money_number}', 'success')
        return redirect(url_for('my_tickets'))
    
    return render_template('attendee/checkout.html', event=event, ticket_types=ticket_types)

@app.route('/my-tickets')
@login_required
def my_tickets():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    
    for booking in bookings:
        if booking.status == 'confirmed':
            qr_data = f"TICKET:{booking.id}:{booking.event.title}:{booking.attendee_name}:{booking.ticket_type}:{booking.quantity}"
            booking.qr_code = generate_qr_code(qr_data)
    
    return render_template('attendee/my_tickets.html', bookings=bookings)

# ==================== SUPPORT ROUTES ====================

@app.route('/support/ticket', methods=['POST'])
@login_required
def support_ticket():
    subject = request.form['subject']
    message = request.form['message']
    
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=subject,
        message=message,
        status='open'
    )
    db.session.add(ticket)
    db.session.commit()
    
    flash('Support ticket created successfully. We will respond within 24 hours.', 'success')
    return redirect(url_for('help_page'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    pending_events = Event.query.filter_by(status='pending').order_by(Event.created_at.desc()).all()
    pending_payments = Event.query.filter_by(is_paid=False, status='pending').count()
    all_events = Event.query.order_by(Event.created_at.desc()).limit(20).all()
    total_users = User.query.count()
    total_events = Event.query.count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == 'completed').scalar() or 0
    
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         pending_events=pending_events,
                         pending_payments=pending_payments,
                         all_events=all_events,
                         total_users=total_users,
                         total_events=total_events,
                         total_revenue=total_revenue,
                         recent_logs=recent_logs)

@app.route('/admin/events')
@admin_required
def admin_events():
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template('admin/events.html', events=events, categories=EVENT_CATEGORIES)

# Update the admin_approve_event route - REMOVE payment requirement
@app.route('/admin/event/<int:event_id>/approve')
@admin_required
def admin_approve_event(event_id):
    event = Event.query.get_or_404(event_id)
    event.status = 'approved'
    # Auto-set is_paid to True when admin approves (bypass payment for demo)
    event.is_paid = True
    db.session.commit()
    log_audit('approve_event', current_user.id, f'Approved event: {event.title}')
    flash(f'Event "{event.title}" has been approved and is now visible to attendees!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/event/<int:event_id>/reject')
@admin_required
def admin_reject_event(event_id):
    event = Event.query.get_or_404(event_id)
    event.status = 'rejected'
    db.session.commit()
    log_audit('reject_event', current_user.id, f'Rejected event: {event.title}')
    flash(f'Event "{event.title}" has been rejected.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/event/<int:event_id>/delete')
@admin_required
def admin_delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    event_title = event.title
    db.session.delete(event)
    db.session.commit()
    log_audit('delete_event', current_user.id, f'Deleted event: {event_title}')
    flash(f'Event "{event_title}" has been permanently deleted.', 'danger')
    return redirect(url_for('admin_events'))

# Update the force publish route
@app.route('/admin/event/<int:event_id>/force-publish')
@admin_required
def admin_force_publish(event_id):
    event = Event.query.get_or_404(event_id)
    event.is_paid = True
    event.status = 'approved'
    db.session.commit()
    log_audit('force_publish', current_user.id, f'Force published event: {event.title}')
    flash(f'Event "{event.title}" has been force published and is now visible to attendees!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/suspend')
@admin_required
def admin_suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot suspend another admin.', 'danger')
        return redirect(url_for('admin_users'))
    
    user.status = 'suspended' if user.status == 'active' else 'active'
    db.session.commit()
    log_audit('suspend_user', current_user.id, f'User {user.username} status changed to {user.status}')
    flash(f'User "{user.username}" has been {"suspended" if user.status == "suspended" else "activated"}.', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/reset-password')
@admin_required
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = secrets.token_hex(4)
    user.set_password(new_password)
    db.session.commit()
    log_audit('reset_password', current_user.id, f'Reset password for user: {user.username}')
    flash(f'Password for "{user.username}" has been reset to: {new_password}', 'info')
    return redirect(url_for('admin_users'))

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    monthly_revenue = db.session.query(
        db.func.strftime('%Y-%m', Payment.payment_date).label('month'),
        db.func.sum(Payment.amount).label('total')
    ).filter(Payment.status == 'completed').group_by('month').all()
    
    events_by_category = db.session.query(
        Event.category,
        db.func.count(Event.id).label('count')
    ).group_by(Event.category).all()
    
    return render_template('admin/analytics.html', 
                         monthly_revenue=monthly_revenue,
                         events_by_category=events_by_category,
                         categories=EVENT_CATEGORIES)

@app.route('/admin/audit-logs')
@admin_required
def admin_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    return render_template('admin/audit_logs.html', logs=logs)

# ==================== API ROUTES ====================

@app.route('/api/event/<int:event_id>/check-availability')
def check_availability(event_id):
    event = Event.query.get_or_404(event_id)
    ticket_type = request.args.get('ticket_type')
    quantity = int(request.args.get('quantity', 1))
    
    ticket = TicketType.query.filter_by(event_id=event_id, name=ticket_type).first()
    if not ticket:
        return jsonify({'available': False, 'message': 'Invalid ticket type'})
    
    sold_count = sum(b.quantity for b in Booking.query.filter_by(event_id=event_id, ticket_type=ticket_type, status='confirmed').all())
    available = ticket.quantity_available - sold_count
    
    return jsonify({
        'available': available >= quantity,
        'remaining': available,
        'requested': quantity
    })

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ==================== CONTEXT PROCESSORS ====================

@app.context_processor
def utility_processor():
    def format_currency(amount):
        return f"UGX {amount:,.0f}" if amount else "UGX 0"
    
    def format_date(date_obj):
        return date_obj.strftime('%B %d, %Y') if date_obj else ''
    
    return {
        'format_currency': format_currency,
        'format_date': format_date,
        'categories': EVENT_CATEGORIES
    }

# ==================== MAIN ====================

if __name__ == '__main__':
    app.run(debug=True, port=5000)