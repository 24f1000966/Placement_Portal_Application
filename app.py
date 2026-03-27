import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    website = db.Column(db.String(200))
    approval_status = db.Column(db.String(20), default='Pending') 
    user = db.relationship('User', backref=db.backref('company_profile', uselist=False, cascade='all, delete-orphan'))

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False, unique=True)
    contact_info = db.Column(db.String(100))
    resume_file = db.Column(db.String(200)) # stores filename
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False, cascade='all, delete-orphan'))

class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
@app.route('/')
def index():
    return render_template('index.html')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_admin():
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            name="Admin",
            email="admin@iitm.ac.in",
            password=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created")


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        user = User(name=name, email=email, password=password, role='student')
        db.session.add(user)
        db.session.commit()

        profile = StudentProfile(user_id=user.id, roll_no=request.form['roll'])
        db.session.add(profile)
        db.session.commit()

        flash("Student registered successfully")
        return redirect(url_for('login'))

    return render_template('register_stud.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        user = User(name=name, email=email, password=password, role='company')
        db.session.add(user)
        db.session.commit()

        company = CompanyProfile(
            user_id=user.id,
            company_name=request.form['company_name']
        )
        db.session.add(company)
        db.session.commit()

        flash("Company registered. Waiting for admin approval.")
        return redirect(url_for('login'))

    return render_template('register_comp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            # Company approval check
            if user.role == 'company':
                if user.company_profile.approval_status != 'Approved':
                    flash("Company not approved by admin yet")
                    return redirect(url_for('login'))

            login_user(user)

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'company':
                return redirect(url_for('company_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))

        flash("Invalid credentials")
    return render_template('login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Unauthorized", 403

    companies = CompanyProfile.query.all()
    return render_template('admin_dash.html', companies=companies)

@app.route('/company/dashboard')
@login_required
def company_dashboard():
    if current_user.role != 'company':
        return "Unauthorized", 403

    return render_template('company_dash.html')

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return "Unauthorized", 403

    return render_template('stud_dash.html')

@app.route('/admin/approve/<int:company_id>')
@login_required
def approve_company(company_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403

    company = CompanyProfile.query.get(company_id)
    company.approval_status = 'Approved'
    db.session.commit()

    flash("Company approved")
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True)
