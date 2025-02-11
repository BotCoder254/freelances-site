from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import User
from bson import ObjectId
import datetime

freelancers = Blueprint('freelancers', __name__)

@freelancers.route('/freelancers')
def list_freelancers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    skills = request.form.getlist('skills')
    
    freelancers_data, total = User.search_freelancers(
        query=search,
        skills=skills if skills else None,
        page=page
    )
    
    return render_template('freelancers/list.html',
                         freelancers=freelancers_data,
                         page=page,
                         total=total,
                         search=search,
                         selected_skills=skills)

@freelancers.route('/freelancers/<freelancer_id>')
def view_freelancer(freelancer_id):
    freelancer = User.get_by_id(freelancer_id)
    if not freelancer or freelancer.account_type != 'freelancer':
        flash('Freelancer not found.', 'error')
        return redirect(url_for('freelancers.list_freelancers'))
    
    # Get freelancer's completed projects
    completed_projects = current_app.db.projects.find({
        'proposals': {
            '$elemMatch': {
                'freelancer_id': ObjectId(freelancer_id),
                'status': 'completed'
            }
        }
    }).limit(5)
    
    return render_template('freelancers/view.html',
                         freelancer=freelancer,
                         completed_projects=completed_projects)

@freelancers.route('/freelancers/<freelancer_id>/reviews', methods=['GET', 'POST'])
@login_required
def review_freelancer(freelancer_id):
    freelancer = User.get_by_id(freelancer_id)
    if not freelancer or freelancer.account_type != 'freelancer':
        flash('Freelancer not found.', 'error')
        return redirect(url_for('freelancers.list_freelancers'))
    
    if request.method == 'POST':
        # Check if the client has worked with the freelancer
        project = current_app.db.projects.find_one({
            'client_id': ObjectId(current_user.id),
            'proposals': {
                '$elemMatch': {
                    'freelancer_id': ObjectId(freelancer_id),
                    'status': 'completed'
                }
            }
        })
        
        if not project:
            flash('You can only review freelancers you have worked with.', 'error')
            return redirect(url_for('freelancers.view_freelancer', freelancer_id=freelancer_id))
        
        review_data = {
            'client_id': ObjectId(current_user.id),
            'rating': int(request.form.get('rating')),
            'comment': request.form.get('comment'),
            'project_id': project['_id'],
            'created_at': datetime.datetime.utcnow()
        }
        
        current_app.db.reviews.insert_one(review_data)
        flash('Review submitted successfully!', 'success')
        return redirect(url_for('freelancers.view_freelancer', freelancer_id=freelancer_id))
    
    # Get existing reviews
    reviews = current_app.db.reviews.find({
        'freelancer_id': ObjectId(freelancer_id)
    }).sort('created_at', -1)
    
    # Get clients who wrote the reviews
    clients = {
        str(review['client_id']): User.get_by_id(str(review['client_id']))
        for review in reviews
    }
    
    return render_template('freelancers/reviews.html',
                         freelancer=freelancer,
                         reviews=reviews,
                         clients=clients)

@freelancers.route('/freelancers/dashboard')
@login_required
def dashboard():
    if current_user.account_type != 'freelancer':
        flash('Access denied. This page is for freelancers only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get active proposals
    active_proposals = current_app.db.projects.find({
        'proposals': {
            '$elemMatch': {
                'freelancer_id': ObjectId(current_user.id),
                'status': {'$in': ['pending', 'accepted']}
            }
        }
    })
    
    # Get completed projects
    completed_projects = current_app.db.projects.find({
        'proposals': {
            '$elemMatch': {
                'freelancer_id': ObjectId(current_user.id),
                'status': 'completed'
            }
        }
    })
    
    # Get recent reviews
    recent_reviews = current_app.db.reviews.find({
        'freelancer_id': ObjectId(current_user.id)
    }).sort('created_at', -1).limit(5)

    # Create pagination object
    pagination = {
        'page': 1,
        'pages': 1,
        'has_prev': False,
        'has_next': False,
        'total': 0
    }
    
    return render_template('dashboard/freelancer_dashboard.html',
                         active_proposals=active_proposals,
                         completed_projects=completed_projects,
                         recent_reviews=recent_reviews,
                         pagination=pagination)

@freelancers.route('/freelancers/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.account_type != 'freelancer':
        flash('Access denied. This page is for freelancers only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        update_data = {
            'bio': request.form.get('bio'),
            'skills': request.form.getlist('skills'),
            'hourly_rate': float(request.form.get('hourly_rate')),
            'social_links': {
                'github': request.form.get('github'),
                'linkedin': request.form.get('linkedin'),
                'website': request.form.get('website')
            }
        }
        
        current_user.update_profile(update_data)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('freelancers.dashboard'))
    
    return render_template('profile/edit_profile.html')

@freelancers.route('/freelancers/portfolio/add', methods=['POST'])
@login_required
def add_portfolio_item():
    if current_user.account_type != 'freelancer':
        flash('Access denied. This page is for freelancers only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    image_url = request.form.get('image_url')
    project_url = request.form.get('project_url')
    
    if not all([title, description, image_url]):
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('freelancers.dashboard'))
    
    success = current_user.add_portfolio_item(
        title=title,
        description=description,
        image_url=image_url,
        project_url=project_url
    )
    
    if success:
        flash('Portfolio item added successfully!', 'success')
    else:
        flash('Failed to add portfolio item.', 'error')
    
    return redirect(url_for('freelancers.dashboard')) 