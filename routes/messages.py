from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import User
from bson import ObjectId
import datetime

messages = Blueprint('messages', __name__)

@messages.route('/messages/create/<recipient_id>', methods=['GET', 'POST'])
@login_required
def create(recipient_id):
    recipient = User.get_by_id(recipient_id)
    if not recipient:
        flash('User not found.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        message_data = {
            'sender_id': ObjectId(current_user.id),
            'recipient_id': ObjectId(recipient_id),
            'subject': request.form.get('subject'),
            'content': request.form.get('content'),
            'created_at': datetime.datetime.utcnow(),
            'read': False
        }
        
        current_app.db.messages.insert_one(message_data)
        flash('Message sent successfully!', 'success')
        return redirect(url_for('messages.inbox'))
    
    return render_template('messages/create.html', recipient=recipient)

@messages.route('/messages/inbox')
@login_required
def inbox():
    messages = current_app.db.messages.find({
        'recipient_id': ObjectId(current_user.id)
    }).sort('created_at', -1)
    
    return render_template('messages/inbox.html', messages=messages) 