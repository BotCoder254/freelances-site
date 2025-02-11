from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from flask import current_app
import datetime

class User(UserMixin):
    ROLE_FREELANCER = 'freelancer'
    ROLE_CLIENT = 'client'

    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data.get('email')
        self.first_name = user_data.get('first_name')
        self.last_name = user_data.get('last_name')
        self.account_type = user_data.get('account_type')
        self.avatar_url = user_data.get('avatar_url')
        self.created_at = user_data.get('created_at')
        self.is_verified = user_data.get('is_verified', False)
        self.skills = user_data.get('skills', [])
        self.bio = user_data.get('bio', '')
        self.hourly_rate = user_data.get('hourly_rate')
        self.portfolio_items = user_data.get('portfolio_items', [])
        self.social_links = user_data.get('social_links', {})
        self.last_login = user_data.get('last_login')
        self.login_count = user_data.get('login_count', 0)
        self.status = user_data.get('status', 'active')

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_freelancer(self):
        return self.account_type == self.ROLE_FREELANCER

    @property
    def is_client(self):
        return self.account_type == self.ROLE_CLIENT

    def get_dashboard_url(self):
        if self.is_freelancer:
            return '/projects/dashboard/freelancer'
        return '/projects/dashboard/client'

    @staticmethod
    def create_user(email, password, first_name, last_name, account_type):
        if User.get_by_email(email):
            return None

        if account_type not in [User.ROLE_FREELANCER, User.ROLE_CLIENT]:
            return None

        user_data = {
            'email': email.lower(),
            'password': generate_password_hash(password),
            'first_name': first_name,
            'last_name': last_name,
            'account_type': account_type,
            'created_at': datetime.datetime.utcnow(),
            'is_verified': False,
            'avatar_url': None,
            'skills': [],
            'bio': '',
            'hourly_rate': None,
            'portfolio_items': [],
            'social_links': {},
            'last_login': None,
            'login_count': 0,
            'status': 'active'
        }

        result = current_app.db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        return User(user_data)

    @staticmethod
    def get_by_id(user_id):
        try:
            user_data = current_app.db.users.find_one({'_id': ObjectId(user_id)})
            return User(user_data) if user_data else None
        except:
            return None

    @staticmethod
    def get_by_email(email):
        user_data = current_app.db.users.find_one({'email': email.lower()})
        return User(user_data) if user_data else None

    def check_password(self, password):
        user_data = current_app.db.users.find_one({'_id': ObjectId(self.id)})
        return check_password_hash(user_data['password'], password)

    def update_login_info(self):
        update_data = {
            'last_login': datetime.datetime.utcnow(),
            'login_count': self.login_count + 1
        }
        current_app.db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': update_data}
        )
        self.last_login = update_data['last_login']
        self.login_count = update_data['login_count']

    def update_profile(self, update_data):
        # Remove sensitive fields that shouldn't be updated directly
        for field in ['password', 'email', 'account_type', 'status']:
            update_data.pop(field, None)

        current_app.db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': update_data}
        )
        # Update instance attributes
        for key, value in update_data.items():
            setattr(self, key, value)

    def add_portfolio_item(self, title, description, image_url, project_url=None):
        if not self.is_freelancer:
            return False

        portfolio_item = {
            'id': str(ObjectId()),
            'title': title,
            'description': description,
            'image_url': image_url,
            'project_url': project_url,
            'created_at': datetime.datetime.utcnow()
        }
        current_app.db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$push': {'portfolio_items': portfolio_item}}
        )
        if not hasattr(self, 'portfolio_items'):
            self.portfolio_items = []
        self.portfolio_items.append(portfolio_item)
        return True

    def remove_portfolio_item(self, item_id):
        if not self.is_freelancer:
            return False

        current_app.db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$pull': {'portfolio_items': {'id': item_id}}}
        )
        self.portfolio_items = [item for item in self.portfolio_items if item['id'] != item_id]
        return True

    def update_social_links(self, social_links):
        current_app.db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': {'social_links': social_links}}
        )
        self.social_links = social_links

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_proposal(self, project):
        if not self.is_freelancer or not project:
            return False
        proposals = project.get('proposals', [])
        return any(str(proposal.get('freelancer_id', '')) == self.id for proposal in proposals)

    @staticmethod
    def search_freelancers(query=None, skills=None, page=1, per_page=10):
        filter_query = {'account_type': User.ROLE_FREELANCER, 'status': 'active'}
        
        if query:
            filter_query['$or'] = [
                {'first_name': {'$regex': query, '$options': 'i'}},
                {'last_name': {'$regex': query, '$options': 'i'}},
                {'bio': {'$regex': query, '$options': 'i'}}
            ]
        
        if skills:
            filter_query['skills'] = {'$all': skills}

        total = current_app.db.users.count_documents(filter_query)
        users_data = current_app.db.users.find(filter_query) \
            .skip((page - 1) * per_page) \
            .limit(per_page)

        return [User(user_data) for user_data in users_data], total 