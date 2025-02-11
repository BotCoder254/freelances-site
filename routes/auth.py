from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from werkzeug.security import generate_password_hash
from functools import wraps

auth = Blueprint('auth', __name__)

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.account_type != role:
                flash('Access denied. You do not have permission to view this page.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.get_by_email(email)

        if not user or not user.check_password(password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        user.update_login_info()

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(user.get_dashboard_url())

    return render_template('auth/login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())

    account_type = request.args.get('type', User.ROLE_CLIENT)
    if account_type not in [User.ROLE_FREELANCER, User.ROLE_CLIENT]:
        account_type = User.ROLE_CLIENT

    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        account_type = request.form.get('account_type')

        if not all([email, first_name, last_name, password, confirm_password, account_type]):
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('auth.signup'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.signup'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('auth.signup'))

        if User.get_by_email(email):
            flash('Email address already exists.', 'error')
            return redirect(url_for('auth.signup'))

        if account_type not in [User.ROLE_FREELANCER, User.ROLE_CLIENT]:
            flash('Invalid account type selected.', 'error')
            return redirect(url_for('auth.signup'))

        user = User.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            account_type=account_type
        )

        if user:
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(user.get_dashboard_url())
        else:
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth.signup'))

    return render_template('auth/signup.html', selected_type=account_type)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.get_by_email(email)
        
        if user:
            # Here you would typically:
            # 1. Generate a password reset token
            # 2. Send an email with the reset link
            # 3. Save the token in the database with an expiration
            flash('If an account exists with that email, you will receive password reset instructions.', 'info')
        else:
            # We don't want to reveal if an email exists or not
            flash('If an account exists with that email, you will receive password reset instructions.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())

    # Here you would:
    # 1. Verify the token is valid and not expired
    # 2. If valid, allow the user to set a new password
    # 3. Update the password in the database
    # 4. Invalidate the token
    
    if request.method == 'POST':
        # Implementation for password reset
        pass
    
    return render_template('auth/reset_password.html') 