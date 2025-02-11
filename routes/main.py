from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import User

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_freelancer:
        return redirect(url_for('projects.freelancer_dashboard'))
    else:
        return redirect(url_for('projects.client_dashboard'))

@main.route('/profile')
@login_required
def profile():
    return render_template('profile/view_profile.html', user=current_user)

@main.route('/edit-profile')
@login_required
def edit_profile():
    return render_template('profile/edit_profile.html', user=current_user)

@main.route('/terms')
def terms():
    return render_template('legal/terms.html')

@main.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')

@main.route('/about')
def about():
    return render_template('about.html')

@main.route('/contact')
def contact():
    return render_template('contact.html') 