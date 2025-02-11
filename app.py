from flask import Flask, render_template
from flask_login import LoginManager
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
    app.config['MONGODB_URI'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/freelancehub')

    # Initialize MongoDB
    client = MongoClient(app.config['MONGODB_URI'])
    app.db = client.get_database()

    # Initialize Login Manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)

    # Custom template filters
    @app.template_filter('timeago')
    def timeago(date):
        if not date:
            return ''
            
        now = datetime.utcnow()
        diff = now - date

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"

    @app.template_filter('date')
    def format_date(date):
        if not date:
            return ''
        return date.strftime('%B %d, %Y')

    # Register blueprints
    from routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from routes.projects import projects as projects_blueprint
    app.register_blueprint(projects_blueprint)

    from routes.freelancers import freelancers as freelancers_blueprint
    app.register_blueprint(freelancers_blueprint)

    from routes.messages import messages as messages_blueprint
    app.register_blueprint(messages_blueprint)

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) 