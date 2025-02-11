from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from models import User
from werkzeug.utils import secure_filename
import os
from bson import ObjectId
import datetime

main = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

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

@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        update_data = {}
        
        # Common fields for both freelancers and clients
        update_data['bio'] = request.form.get('bio', '')
        update_data['social_links'] = {
            'github': request.form.get('github', ''),
            'linkedin': request.form.get('linkedin', ''),
            'website': request.form.get('website', '')
        }

        if current_user.is_freelancer:
            # Freelancer specific fields
            update_data['hourly_rate'] = float(request.form.get('hourly_rate', 0))
            update_data['skills'] = [skill.strip() for skill in request.form.get('skills', '').split(',') if skill.strip()]
        else:
            # Client specific fields
            update_data['company_name'] = request.form.get('company_name', '')
            update_data['industry'] = request.form.get('industry', '')
            update_data['company_size'] = request.form.get('company_size', '')

        current_user.update_profile(update_data)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))

    return render_template('profile/edit_profile.html', user=current_user)

@main.route('/update-avatar', methods=['POST'])
@login_required
def update_avatar():
    if 'avatar' not in request.files:
        return {'error': 'No file provided'}, 400
    
    file = request.files['avatar']
    if file.filename == '':
        return {'error': 'No file selected'}, 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{file.filename.rsplit('.', 1)[1]}")
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        avatar_url = url_for('static', filename=f'uploads/avatars/{filename}')
        current_user.update_profile({'avatar_url': avatar_url})
        
        return {'success': True, 'avatar_url': avatar_url}
    
    return {'error': 'Invalid file type'}, 400

@main.route('/add-portfolio', methods=['POST'])
@login_required
def add_portfolio():
    if not current_user.is_freelancer:
        return {'error': 'Only freelancers can add portfolio items'}, 403
    
    title = request.form.get('title')
    description = request.form.get('description')
    project_url = request.form.get('project_url')
    
    if 'image' not in request.files:
        return {'error': 'No image provided'}, 400
    
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return {'error': 'Invalid file'}, 400
    
    filename = secure_filename(f"portfolio_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{file.filename.rsplit('.', 1)[1]}")
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'portfolio')
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    image_url = url_for('static', filename=f'uploads/portfolio/{filename}')
    current_user.add_portfolio_item(title, description, image_url, project_url)
    
    return {'success': True}

@main.route('/delete-portfolio/<item_id>', methods=['POST'])
@login_required
def delete_portfolio(item_id):
    if not current_user.is_freelancer:
        return {'error': 'Only freelancers can delete portfolio items'}, 403
    
    success = current_user.remove_portfolio_item(item_id)
    if success:
        return {'success': True}
    return {'error': 'Failed to delete portfolio item'}, 400

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