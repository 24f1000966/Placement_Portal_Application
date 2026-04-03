import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory, g, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.local import LocalProxy
from werkzeug.security import generate_password_hash, check_password_hash

class UserMixin:
    is_authenticated = True

class DummyAnonymousUser:
    is_authenticated = False
    is_active = False
    role = None

def get_current_user():
    if hasattr(g, 'user'): return g.user
    path = request.path
    role = None
    if path.startswith('/admin'): role = 'admin'
    elif path.startswith('/company'): role = 'company'
    elif path.startswith('/student'): role = 'student'
    if not role: role = session.get('active_role')
    
    user_id = session.get(f'{role}_id') if role else None
    if user_id:
        user = User.query.get(user_id)
        if user:
            g.user = user
            return user
    return DummyAnonymousUser()

current_user = LocalProxy(get_current_user)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def login_user(user):
    session[f'{user.role}_id'] = user.id
    session['active_role'] = user.role

def logout_user():
    path = request.referrer or request.path
    role_to_pop = None
    
    if '/admin' in path: role_to_pop = 'admin'
    elif '/company' in path: role_to_pop = 'company'
    elif '/student' in path: role_to_pop = 'student'
    else: role_to_pop = session.get('active_role')
    
    if role_to_pop and f'{role_to_pop}_id' in session:
        session.pop(f'{role_to_pop}_id', None)
        
    # Reassign active_role to any surviving session
    for r in ['admin', 'student', 'company']:
        if f'{r}_id' in session:
            session['active_role'] = r
            return
            
    session.pop('active_role', None)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'placement_secret_key_999_updated'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_NAME'] = 'placement_portal_session'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) 
    is_active = db.Column(db.Boolean, default=True)

class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    hr_contact = db.Column(db.String(100))
    contact_email = db.Column(db.String(120))
    contact_number = db.Column(db.String(50))
    hr_contact_number = db.Column(db.String(50))
    linkedin_id = db.Column(db.String(100))
    website = db.Column(db.String(200))
    about = db.Column(db.Text)
    approval_status = db.Column(db.String(20), default='Pending') 
    user = db.relationship('User', backref=db.backref('company_profile', uselist=False, cascade='all, delete-orphan'))

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False, unique=True)
    contact_info = db.Column(db.String(100))
    linkedin_id = db.Column(db.String(100))
    skills = db.Column(db.Text)
    hobbies = db.Column(db.String(200))
    cgpa = db.Column(db.Float)
    institution_name = db.Column(db.String(200))
    education = db.Column(db.String(100))
    resume_file = db.Column(db.String(200)) # stores filename
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False, cascade='all, delete-orphan'))

class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salary = db.Column(db.Integer, default="Not to Disclose")
    location = db.Column(db.String(100),default="Remote")
    job_type = db.Column(db.String(50),default="Full-time")
    experience = db.Column(db.String(50),default="Fresher")
    company_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    eligibility = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Pending') 
    company = db.relationship('User', backref=db.backref('drives', cascade='all, delete-orphan'))

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.id'), nullable=False)
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Applied') 
    student = db.relationship('User', backref=db.backref('applications', cascade='all, delete-orphan'))
    drive = db.relationship('PlacementDrive', backref=db.backref('applications', cascade='all, delete-orphan'))

    __table_args__ = (db.UniqueConstraint('student_user_id', 'drive_id', name='uq_student_drive'),)

# Decorators
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash(f'Access Denied. You are currently logged in as a {current_user.role}.', 'danger')
            if current_user.role == 'company': return redirect(url_for('company_dashboard'))
            elif current_user.role == 'student': return redirect(url_for('student_dashboard'))
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def company_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if current_user.role != 'company':
            flash(f'Access Denied. You are currently logged in as a {current_user.role}.', 'danger')
            if current_user.role == 'admin': return redirect(url_for('admin_dashboard'))
            elif current_user.role == 'student': return redirect(url_for('student_dashboard'))
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if current_user.role != 'student':
            flash(f'Access Denied. You are currently logged in as a {current_user.role}.', 'danger')
            if current_user.role == 'admin': return redirect(url_for('admin_dashboard'))
            elif current_user.role == 'company': return redirect(url_for('company_dashboard'))
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_active():
    if current_user.is_authenticated and not current_user.is_active:
        logout_user()
        flash('Your account has been blacklisted or deactivated.', 'danger')
        return redirect(url_for('login'))

# routing starts frm here
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            if not user.is_active:
                flash('Your account has been blacklisted or deactivated.', 'danger')
                return render_template('login.html')
            login_user(user)
            if user.role == 'admin': return redirect(url_for('admin_dashboard'))
            elif user.role == 'company': return redirect(url_for('company_dashboard'))
            elif user.role == 'student': return redirect(url_for('student_dashboard'))
        else:
            flash('Login failed. Check email and password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        roll_no = request.form.get('roll_no')
        contact_info = request.form.get('contact_info')
        
        if User.query.filter_by(email=email).first() or StudentProfile.query.filter_by(roll_no=roll_no).first():
            flash('Email or Roll No already exists.', 'danger')
            return redirect(url_for('register_student'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role='student')
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = StudentProfile(user_id=new_user.id, roll_no=roll_no, contact_info=contact_info)
        db.session.add(new_profile)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register_student.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name')
        hr_contact = request.form.get('hr_contact')
        website = request.form.get('website')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register_company'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role='company')
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = CompanyProfile(user_id=new_user.id, company_name=company_name, hr_contact=hr_contact, website=website)
        db.session.add(new_profile)
        db.session.commit()
        
        flash('Registration successful! Wait for admin approval.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register_company.html')

# dmin Routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    search = request.args.get('search', '')
    
    if search:
        students = StudentProfile.query.join(User).filter(
            db.or_(User.name.ilike(f'%{search}%'), StudentProfile.roll_no.ilike(f'%{search}%'))
        ).all()
        companies = CompanyProfile.query.join(User).filter(
            db.or_(CompanyProfile.company_name.ilike(f'%{search}%'), User.name.ilike(f'%{search}%'))
        ).all()
        pending_companies = []
    else:
        students = StudentProfile.query.all()
        companies = CompanyProfile.query.filter(CompanyProfile.approval_status != 'Pending').all()
        pending_companies = CompanyProfile.query.filter_by(approval_status='Pending').all()
        
    drives = PlacementDrive.query.filter(PlacementDrive.status.in_(['Approved', 'Pending'])).all()
    
    total_students = StudentProfile.query.count()
    total_companies = CompanyProfile.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    
    return render_template('admin_dashboard.html', 
                           students=students, 
                           companies=companies, 
                           pending_companies=pending_companies,
                           drives=drives,
                           search=search,
                           total_students=total_students,
                           total_companies=total_companies,
                           total_drives=total_drives,
                           total_applications=total_applications)

@app.route('/admin/approve-company/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_approve_company(id):
    company = CompanyProfile.query.get_or_404(id)
    status = request.form.get('status')
    if status in ['Approved', 'Rejected']:
        company.approval_status = status
        db.session.commit()
        flash(f'Company status updated to {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/blacklist-company/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_blacklist_company(id):
    company = CompanyProfile.query.get_or_404(id)
    user = company.user
    user.is_active = not user.is_active
    
    if not user.is_active:
        for drive in user.drives:
            if drive.status == 'Approved':
                drive.status = 'Closed'
                
    db.session.commit()
    status_str = "activated" if user.is_active else "blacklisted"
    flash(f'Company {company.company_name} has been {status_str}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/blacklist-student/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_blacklist_student(id):
    student = StudentProfile.query.get_or_404(id)
    user = student.user
    user.is_active = not user.is_active
    db.session.commit()
    status_str = "activated" if user.is_active else "blacklisted"
    flash(f'Student {user.name} has been {status_str}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve-drive/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_approve_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    status = request.form.get('status')
    if status in ['Approved', 'Rejected']:
        drive.status = status
        db.session.commit()
        flash(f'Drive status updated to {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/complete-drive/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_complete_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    drive.status = 'Closed'
    db.session.commit()
    flash(f'Drive {drive.job_title} marked as completed.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/company/<int:company_id>/view')
@login_required
@admin_required
def admin_company_profile(company_id):
    company = CompanyProfile.query.get_or_404(company_id)
    return render_template('admin_view_company.html', company=company)

@app.route('/admin/view-applications')
@login_required
@admin_required
def admin_view_applications():
    drive_id = request.args.get('drive_id')
    drive = None
    if drive_id:
        applications = Application.query.filter_by(drive_id=drive_id).all()
        drive = PlacementDrive.query.get(drive_id)
        subtitle = f"for {drive.job_title} ({drive.company.company_profile.company_name})" if drive else ""
    else:
        applications = Application.query.all()
        subtitle = "All Applications"
        
    return render_template('admin_applications.html', applications=applications, subtitle=subtitle, drive=drive)



@app.route('/company/dashboard')
@login_required
@company_required
def company_dashboard():
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved yet.', 'warning')
        return render_template('company_dashboard.html', approved=False)
        
    upcoming_drives = PlacementDrive.query.filter(
        PlacementDrive.company_user_id == current_user.id,
        PlacementDrive.status.in_(['Approved', 'Ongoing', 'Pending'])
    ).all()
    
    closed_drives = PlacementDrive.query.filter_by(
        company_user_id=current_user.id, status='Closed'
    ).all()
    
    return render_template('company_dashboard.html', 
                           approved=True, 
                           upcoming_drives=upcoming_drives, 
                           closed_drives=closed_drives)

@app.route('/company/profile', methods=['GET', 'POST'])
@login_required
@company_required
def company_profile():
    if request.method == 'POST':
        current_user.company_profile.company_name = request.form.get('company_name')
        current_user.name = request.form.get('hr_name')
        current_user.company_profile.hr_contact = request.form.get('hr_name')
        current_user.company_profile.contact_email = request.form.get('contact_email')
        current_user.company_profile.contact_number = request.form.get('contact_number')
        current_user.company_profile.hr_contact_number = request.form.get('hr_contact_number')
        current_user.company_profile.website = request.form.get('website')
        current_user.company_profile.linkedin_id = request.form.get('linkedin_id')
        current_user.company_profile.about = request.form.get('about')
        db.session.commit()
        flash('Company profile updated successfully!', 'success')
        return redirect(url_for('company_profile'))
    return render_template('company_profile.html')

@app.route('/company/create-drive', methods=['GET', 'POST'])
@login_required
@company_required
def create_drive():
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
        
    if request.method == 'POST':
        job_title = request.form.get('job_title')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')
        deadline_str = request.form.get('deadline')
        deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        
        new_drive = PlacementDrive(
            company_user_id=current_user.id,
            job_title=job_title,
            job_type=request.form.get('job_type', 'Full-time'),
            experience=request.form.get('experience', 'Fresher'),
            location=request.form.get('location', 'Remote'),
            salary=request.form.get('salary', ''),
            description=description,
            eligibility=eligibility,
            deadline=deadline
        )
        db.session.add(new_drive)
        db.session.commit()
        flash('Drive created successfully! Awaiting admin approval.', 'success')
        return redirect(url_for('company_dashboard'))
        
    return render_template('create_drive.html')

@app.route('/company/edit-drive/<int:drive_id>', methods=['GET', 'POST'])
@login_required
@company_required
def edit_drive(drive_id):
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('company_dashboard'))

    if request.method == 'POST':
        drive.job_title = request.form.get('job_title')
        drive.job_type = request.form.get('job_type', 'Full-time')
        drive.experience = request.form.get('experience', 'Fresher')
        drive.location = request.form.get('location', 'Remote')
        drive.salary = request.form.get('salary', '')
        drive.description = request.form.get('description')
        drive.eligibility = request.form.get('eligibility')
        deadline_str = request.form.get('deadline')
        if deadline_str:
            drive.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('Drive updated successfully.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('edit_drive.html', drive=drive)

@app.route('/company/mark-complete/<int:drive_id>', methods=['POST'])
@login_required
@company_required
def mark_complete(drive_id):
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('company_dashboard'))
    
    drive.status = 'Closed'
    db.session.commit()
    flash('Drive marked as completed.', 'success')
    return redirect(url_for('company_dashboard'))

@app.route('/company/delete-drive/<int:drive_id>', methods=['POST'])
@login_required
@company_required
def delete_drive(drive_id):
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('company_dashboard'))
    
    db.session.delete(drive)
    db.session.commit()
    flash('Drive deleted successfully.', 'success')
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/<int:drive_id>/applications')
@login_required
@company_required
def company_applications(drive_id):
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('company_dashboard'))
        
    applications = Application.query.filter_by(drive_id=drive_id).all()
    return render_template('company_applications.html', drive=drive, applications=applications)

@app.route('/company/application/<int:application_id>', methods=['GET', 'POST'])
@login_required
@company_required
def review_application(application_id):
    if current_user.company_profile.approval_status != 'Approved':
        flash('Your company is not approved.', 'warning')
        return redirect(url_for('company_dashboard'))
    application = Application.query.get_or_404(application_id)
    if application.drive.company_user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('company_dashboard'))
        
    if request.method == 'POST':
        status = request.form.get('status')
        if status in ['Shortlisted', 'Selected', 'Rejected']:
            application.status = status
            db.session.commit()
            flash('Application status saved successfully.', 'success')
        return redirect(url_for('company_applications', drive_id=application.drive_id))
        
    return render_template('review_application.html', application=application)



@app.route('/student/<int:student_id>/view')
@login_required
def view_student_profile(student_id):
    if current_user.role not in ['admin', 'company']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
        
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        abort(404)
        
    return render_template('view_student_profile.html', student=student)

@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    approved_companies = CompanyProfile.query.filter_by(approval_status='Approved').all()
    applications = Application.query.filter_by(student_user_id=current_user.id).all()
    approved_drives = PlacementDrive.query.filter_by(status='Approved').all()
    
    status_alerts = []
    for app in applications:
        if app.status in ['Selected', 'Shortlisted']:
            status_alerts.append({'type': 'success', 'message': f"Congratulations! You've been {app.status} for {app.drive.job_title} at {app.drive.company.company_profile.company_name}."})
        elif app.status == 'Rejected':
            status_alerts.append({'type': 'danger', 'message': f"Update: Your application for {app.drive.job_title} at {app.drive.company.company_profile.company_name} was {app.status}."})

    return render_template('student_dashboard.html', 
                           companies=approved_companies, 
                           approved_drives=approved_drives,
                           applications=applications,
                           status_alerts=status_alerts)

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
@student_required
def student_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.student_profile.contact_info = request.form.get('contact_info')
        current_user.student_profile.linkedin_id = request.form.get('linkedin_id')
        current_user.student_profile.skills = request.form.get('skills')
        current_user.student_profile.institution_name = request.form.get('institution_name')
        current_user.student_profile.hobbies = request.form.get('hobbies')
        current_user.student_profile.education = request.form.get('education')
        cgpa_val = request.form.get('cgpa')
        if cgpa_val:
            try:
                current_user.student_profile.cgpa = float(cgpa_val)
            except ValueError:
                pass
        
        file = request.files.get('resume')
        if file and file.filename != '':
            filename = secure_filename(f"resume_{current_user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.student_profile.resume_file = filename
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))
    return render_template('student_profile.html')

@app.route('/student/company/<int:company_id>')
@login_required
@student_required
def student_company(company_id):
    company = CompanyProfile.query.get_or_404(company_id)
    if company.approval_status != 'Approved':
        flash('Company not available.', 'danger')
        return redirect(url_for('student_dashboard'))
    drives = PlacementDrive.query.filter(PlacementDrive.company_user_id == company.user_id, PlacementDrive.status == 'Approved').all()
    return render_template('student_company.html', company=company, drives=drives)

@app.route('/student/drive/<int:drive_id>')
@login_required
@student_required
def student_drive(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.status != 'Approved':
        flash('Drive not available.', 'danger')
        return redirect(url_for('student_dashboard'))
    already_applied = Application.query.filter_by(student_user_id=current_user.id, drive_id=drive_id).first() is not None
    return render_template('student_drive.html', drive=drive, already_applied=already_applied)

@app.route('/student/apply/<int:drive_id>', methods=['POST'])
@login_required
@student_required
def student_apply(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.status != 'Approved' or drive.deadline < datetime.utcnow():
        flash('Cannot apply to this drive right now.', 'danger')
        return redirect(url_for('student_drive', drive_id=drive_id))
        
    existing = Application.query.filter_by(student_user_id=current_user.id, drive_id=drive_id).first()
    if existing:
        flash('Already applied.', 'warning')
        return redirect(url_for('student_drive', drive_id=drive_id))
        
    new_application = Application(student_user_id=current_user.id, drive_id=drive_id)
    db.session.add(new_application)
    db.session.commit()
    flash('Successfully applied to the placement drive!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/history')
@login_required
@student_required
def student_history():
    applications = Application.query.filter_by(student_user_id=current_user.id).all()
    return render_template('student_history.html', applications=applications)
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(role='admin').first():
            admin = User(name='Admin', email='admin@admin.com', password=generate_password_hash('admin'), role='admin')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created (admin@admin.com / admin)")

if __name__ == '__main__':
    if not os.path.exists('placement.db'):
        init_db()
    app.run(debug=True, port=5002)
