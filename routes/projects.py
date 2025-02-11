from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file
from flask_login import login_required, current_user
from bson import ObjectId
from datetime import datetime
from models import User
import os
from werkzeug.utils import secure_filename

projects = Blueprint('projects', __name__)

@projects.route('/projects')
def list_projects():
    page = request.args.get('page', 1, type=int)
    per_page = 9  # Number of projects per page
    search = request.args.get('q', '')
    category = request.args.get('category', '')
    budget = request.args.get('budget', '')
    status = request.args.get('status', 'open')  # Add status filter

    # Build the filter query
    filter_query = {'status': status}
    if search:
        filter_query['$or'] = [
            {'title': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}}
        ]
    if category:
        filter_query['category'] = category
    if budget:
        min_budget, max_budget = budget.split('-') if '-' in budget else (budget.replace('+', ''), None)
        if max_budget:
            filter_query['budget_min'] = {'$gte': float(min_budget), '$lte': float(max_budget)}
        else:
            filter_query['budget_min'] = {'$gte': float(min_budget)}

    # Get total count for pagination
    total = current_app.db.projects.count_documents(filter_query)
    
    # Calculate pagination values
    offset = (page - 1) * per_page
    total_pages = (total + per_page - 1) // per_page

    # Get projects for current page
    projects_cursor = current_app.db.projects.find(filter_query) \
        .sort('created_at', -1) \
        .skip(offset) \
        .limit(per_page)

    # Convert cursor to list and enhance project data
    projects_list = []
    for project in projects_cursor:
        # Get client info
        client = current_app.db.users.find_one({'_id': project['client_id']})
        if client:
            project['client'] = {
                'name': f"{client.get('first_name', '')} {client.get('last_name', '')}",
                'avatar_url': client.get('avatar_url'),
                'hire_rate': client.get('hire_rate', 0)
            }
        projects_list.append(project)

    # Create pagination object
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1,
        'next_num': page + 1,
        'iter_pages': lambda: range(1, total_pages + 1)
    }

    # Get all categories for filter dropdown
    categories = current_app.db.projects.distinct('category')

    return render_template('projects/list.html',
                         projects=projects_list,
                         pagination=pagination,
                         categories=categories,
                         search=search,
                         selected_category=category,
                         selected_budget=budget,
                         status=status)

@projects.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if current_user.account_type != 'client':
        flash('Only clients can create projects.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # Handle file uploads
        attachments = []
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    # Check file type
                    allowed_extensions = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
                    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                        filename = secure_filename(file.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{filename}"
                        file_path = os.path.join('static', 'uploads', 'projects', unique_filename)
                        
                        # Ensure upload directory exists
                        os.makedirs(os.path.join('static', 'uploads', 'projects'), exist_ok=True)
                        
                        # Save file
                        file.save(file_path)
                        attachments.append({
                            'filename': filename,
                            'path': file_path,
                            'type': file.filename.rsplit('.', 1)[1].lower(),
                            'uploaded_at': datetime.utcnow()
                        })

        project_data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'category': request.form.get('category'),
            'budget_min': float(request.form.get('budget_min')),
            'budget_max': float(request.form.get('budget_max')),
            'deadline': datetime.strptime(request.form.get('deadline'), '%Y-%m-%d'),
            'skills_required': [skill.strip() for skill in request.form.get('skills').split(',') if skill.strip()],
            'client_id': ObjectId(current_user.id),
            'status': 'open',
            'created_at': datetime.utcnow(),
            'proposals': [],
            'attachments': attachments,
            'visibility': request.form.get('visibility', 'public'),
            'views': 0,
            'last_updated': datetime.utcnow()
        }
        
        result = current_app.db.projects.insert_one(project_data)
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=str(result.inserted_id)))
    
    return render_template('projects/create.html')

@projects.route('/projects/<project_id>')
def view_project(project_id):
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    client = User.get_by_id(str(project['client_id']))
    if client:
        project['client'] = {
            'id': client.id,
            'name': client.get_full_name(),
            'avatar_url': client.avatar_url,
            'created_at': client.created_at,
            'projects': list(current_app.db.projects.find({'client_id': ObjectId(client.id)})),
            'hire_rate': len([p for p in project.get('proposals', []) if p.get('status') == 'accepted']) / len(project.get('proposals', [])) if project.get('proposals') else 0
        }
    
    # Get proposals if user is the project owner or a freelancer who submitted a proposal
    proposals = []
    can_view_proposals = False
    
    if current_user.is_authenticated:
        if str(project['client_id']) == current_user.id:
            can_view_proposals = True
            proposals = project.get('proposals', [])
            # Get freelancer details for each proposal
            for proposal in proposals:
                proposal['freelancer'] = User.get_by_id(str(proposal['freelancer_id']))
        else:
            # Check if current freelancer has submitted a proposal
            for proposal in project.get('proposals', []):
                if str(proposal['freelancer_id']) == current_user.id:
                    proposals = [proposal]
                    break
    
    return render_template('projects/view.html',
                         project=project,
                         proposals=proposals,
                         can_view_proposals=can_view_proposals)

@projects.route('/projects/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if str(project['client_id']) != current_user.id:
        flash('You can only edit your own projects.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    if request.method == 'POST':
        # Handle file uploads
        attachments = project.get('attachments', [])
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join('uploads', 'projects', filename)
                    file.save(file_path)
                    attachments.append({
                        'filename': filename,
                        'path': file_path
                    })

        update_data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'category': request.form.get('category'),
            'budget_min': float(request.form.get('budget_min')),
            'budget_max': float(request.form.get('budget_max')),
            'deadline': datetime.strptime(request.form.get('deadline'), '%Y-%m-%d'),
            'skills_required': request.form.get('skills').split(','),
            'attachments': attachments,
            'visibility': request.form.get('visibility', 'public'),
            'updated_at': datetime.utcnow()
        }
        
        current_app.db.projects.update_one(
            {'_id': ObjectId(project_id)},
            {'$set': update_data}
        )
        
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    return render_template('projects/edit.html', project=project)

@projects.route('/projects/<project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if str(project['client_id']) != current_user.id:
        flash('You can only delete your own projects.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Delete project attachments
    for attachment in project.get('attachments', []):
        try:
            os.remove(attachment['path'])
        except:
            pass
    
    current_app.db.projects.delete_one({'_id': ObjectId(project_id)})
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('projects.list_projects'))

@projects.route('/projects/<project_id>/submit-proposal', methods=['GET', 'POST'])
@login_required
def submit_proposal(project_id):
    if not current_user.is_freelancer:
        flash('Only freelancers can submit proposals.', 'error')
        return redirect(url_for('projects.list_projects'))

    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except:
        flash('Invalid project ID.', 'error')
        return redirect(url_for('projects.list_projects'))

    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))

    if current_user.has_proposal(project):
        flash('You have already submitted a proposal for this project.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))

    if request.method == 'POST':
        proposal_data = {
            'freelancer_id': ObjectId(current_user.id),
            'bid_amount': float(request.form.get('bid_amount')),
            'delivery_time': int(request.form.get('delivery_time')),
            'cover_letter': request.form.get('cover_letter'),
            'status': 'pending',
            'created_at': datetime.utcnow()
        }

        current_app.db.projects.update_one(
            {'_id': ObjectId(project_id)},
            {'$push': {'proposals': proposal_data}}
        )

        flash('Your proposal has been submitted successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))

    return render_template('projects/submit_proposal.html', project=project)

@projects.route('/projects/submit-proposal')
def submit_proposal_redirect():
    flash('Please select a project before submitting a proposal.', 'error')
    return redirect(url_for('projects.list_projects'))

@projects.route('/projects/<project_id>/hire/<freelancer_id>', methods=['POST'])
@login_required
def hire_freelancer(project_id, freelancer_id):
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if str(project['client_id']) != current_user.id:
        flash('Only the project owner can hire freelancers.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Update project status and mark the selected proposal as accepted
    current_app.db.projects.update_one(
        {
            '_id': ObjectId(project_id),
            'proposals.freelancer_id': ObjectId(freelancer_id)
        },
        {
            '$set': {
                'status': 'in_progress',
                'hired_freelancer_id': ObjectId(freelancer_id),
                'proposals.$.status': 'accepted',
                'hired_at': datetime.utcnow()
            }
        }
    )
    
    # Update other proposals as rejected
    current_app.db.projects.update_many(
        {
            '_id': ObjectId(project_id),
            'proposals.freelancer_id': {'$ne': ObjectId(freelancer_id)}
        },
        {
            '$set': {
                'proposals.$[].status': 'rejected'
            }
        }
    )
    
    flash('Freelancer hired successfully!', 'success')
    return redirect(url_for('projects.view_project', project_id=project_id))

@projects.route('/projects/<project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if str(project['client_id']) != current_user.id:
        flash('Only the project owner can mark projects as complete.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    current_app.db.projects.update_one(
        {'_id': ObjectId(project_id)},
        {
            '$set': {
                'status': 'completed',
                'completed_at': datetime.utcnow()
            }
        }
    )
    
    flash('Project marked as complete!', 'success')
    return redirect(url_for('projects.view_project', project_id=project_id))

@projects.route('/projects/dashboard/client')
@login_required
def client_dashboard():
    if current_user.account_type != 'client':
        flash('Access denied. This page is for clients only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get all client's projects (both active and pending)
    base_query = {'client_id': ObjectId(current_user.id)}
    
    # Get active and pending projects
    active_projects = list(current_app.db.projects.find({
        **base_query,
        'status': {'$in': ['open', 'in_progress']}
    }).sort('last_updated', -1))
    
    # Get recent proposals across all projects
    recent_proposals = []
    project_ids = [p['_id'] for p in active_projects]
    
    if project_ids:
        projects_with_proposals = current_app.db.projects.find({
            '_id': {'$in': project_ids}
        })
        
        for project in projects_with_proposals:
            for proposal in project.get('proposals', []):
                freelancer = current_app.db.users.find_one({'_id': proposal['freelancer_id']})
                if freelancer:
                    recent_proposals.append({
                        'freelancer': {
                            'id': str(freelancer['_id']),
                            'name': f"{freelancer.get('first_name', '')} {freelancer.get('last_name', '')}",
                            'avatar_url': freelancer.get('avatar_url')
                        },
                        'project': {
                            'id': str(project['_id']),
                            'title': project['title']
                        },
                        'bid_amount': proposal['bid_amount'],
                        'status': proposal['status'],
                        'cover_letter': proposal.get('cover_letter', ''),
                        'created_at': proposal.get('created_at', datetime.utcnow())
                    })
    
    # Sort proposals by date and get the 5 most recent
    recent_proposals.sort(key=lambda x: x['created_at'], reverse=True)
    recent_proposals = recent_proposals[:5]
    
    # Get hired freelancers with real-time status
    hired_freelancers = []
    active_projects = current_app.db.projects.find({
        'client_id': ObjectId(current_user.id),
        'status': 'in_progress',
        'hired_freelancer_id': {'$exists': True}
    })
    
    for project in active_projects:
        if project.get('hired_freelancer_id'):
            freelancer = current_app.db.users.find_one({'_id': project['hired_freelancer_id']})
            if freelancer:
                # Get the accepted proposal for this freelancer
                accepted_proposal = next(
                    (p for p in project.get('proposals', []) 
                     if str(p.get('freelancer_id')) == str(project['hired_freelancer_id']) 
                     and p.get('status') == 'accepted'),
                    None
                )
                
                if accepted_proposal:
                    hired_freelancers.append({
                        'freelancer': {
                            'id': str(freelancer['_id']),
                            'name': f"{freelancer.get('first_name', '')} {freelancer.get('last_name', '')}",
                            'avatar_url': freelancer.get('avatar_url')
                        },
                        'project': {
                            'id': str(project['_id']),
                            'title': project['title']
                        },
                        'rate': accepted_proposal['bid_amount'],
                        'rating': freelancer.get('rating', 0)
                    })
    
    # Enhance projects with additional data
    for project in active_projects:
        project['proposals'] = project.get('proposals', [])
        project['proposal_count'] = len(project['proposals'])
        if project.get('hired_freelancer_id'):
            freelancer = current_app.db.users.find_one({'_id': project['hired_freelancer_id']})
            if freelancer:
                project['hired_freelancer'] = {
                    'name': f"{freelancer.get('first_name', '')} {freelancer.get('last_name', '')}",
                    'avatar_url': freelancer.get('avatar_url')
                }
    
    return render_template('dashboard/client_dashboard.html',
                         active_projects=active_projects,
                         recent_proposals=recent_proposals,
                         hired_freelancers=hired_freelancers)

@projects.route('/projects/dashboard/freelancer')
@login_required
def freelancer_dashboard():
    if current_user.account_type != 'freelancer':
        flash('Access denied. This page is for freelancers only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get active projects (where freelancer is hired)
    active_projects = list(current_app.db.projects.find({
        'hired_freelancer_id': ObjectId(current_user.id),
        'status': 'in_progress'
    }).sort('last_updated', -1))
    
    # Get all proposals by the freelancer
    proposals_query = {
        'proposals': {
            '$elemMatch': {
                'freelancer_id': ObjectId(current_user.id)
            }
        }
    }
    
    total = current_app.db.projects.count_documents(proposals_query)
    
    # Get projects with proposal details
    projects_cursor = current_app.db.projects.find(proposals_query).sort('last_updated', -1).skip((page - 1) * per_page).limit(per_page)
    
    # Enhance project data with client information and real-time status
    projects = []
    for project in projects_cursor:
        # Get client info
        client = current_app.db.users.find_one({'_id': project['client_id']})
        if client:
            project['client'] = {
                'name': f"{client.get('first_name', '')} {client.get('last_name', '')}",
                'avatar_url': client.get('avatar_url'),
                'total_projects': current_app.db.projects.count_documents({'client_id': client['_id']}),
                'completed_projects': current_app.db.projects.count_documents({
                    'client_id': client['_id'],
                    'status': 'completed'
                })
            }
        
        # Get freelancer's specific proposal with real-time status
        for proposal in project.get('proposals', []):
            if str(proposal.get('freelancer_id')) == current_user.id:
                project['user_proposal'] = proposal
                # Add milestone progress if proposal is accepted
                if proposal.get('status') == 'accepted':
                    milestones = current_app.db.milestones.find({
                        'project_id': project['_id'],
                        'freelancer_id': ObjectId(current_user.id)
                    }).sort('created_at', 1)
                    proposal['milestones'] = list(milestones)
                break
        
        # Add file access information for accepted proposals
        if project.get('user_proposal', {}).get('status') == 'accepted':
            project['attachments'] = project.get('attachments', [])
        
        projects.append(project)
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page
    }
    
    return render_template('dashboard/freelancer_dashboard.html',
                         active_projects=active_projects,
                         projects=projects,
                         pagination=pagination)

@projects.route('/projects/<project_id>/download/<path:filename>')
@login_required
def download_file(project_id, filename):
    # Get project
    project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Check if user has access
    has_access = False
    if str(project['client_id']) == current_user.id:
        has_access = True
    elif current_user.is_freelancer:
        # Check if freelancer has an accepted proposal
        for proposal in project.get('proposals', []):
            if (str(proposal.get('freelancer_id')) == current_user.id and 
                proposal.get('status') == 'accepted'):
                has_access = True
                break
    
    if not has_access:
        flash('You do not have permission to access this file.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Find the file in attachments
    attachment = next((a for a in project.get('attachments', []) 
                      if os.path.basename(a['path']) == filename), None)
    if not attachment:
        flash('File not found.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    try:
        return send_file(
            attachment['path'],
            as_attachment=True,
            download_name=attachment['filename']
        )
    except Exception as e:
        flash('Error downloading file.', 'error')
        return redirect(url_for('projects.view_project', project_id=project_id)) 