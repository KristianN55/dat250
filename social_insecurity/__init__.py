"""Provides the social_insecurity package for the Social Insecurity application.

The package contains the Flask application factory.
"""

from pathlib import Path
from shutil import rmtree
from typing import cast

from flask import Flask, current_app
from flask_login import LoginManager

from social_insecurity.config import Config
from social_insecurity.database import SQLite3
from social_insecurity.models import User
from social_insecurity.database import sqlite



# Initialize extensions
sqlite = SQLite3()
login_manager = LoginManager()
login_manager.login_view = "index"


def create_app(test_config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.from_object(test_config)

    # Initialize database
    sqlite.init_app(app, schema="schema.sql")

    # Initialize Flask-Login
    login_manager.init_app(app)

    # Register the user_loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    # Create uploads folder
    with app.app_context():
        create_uploads_folder(app)

    # Import routes after app creation
    with app.app_context():
        import social_insecurity.routes  # noqa: E402,F401

    return app


def create_uploads_folder(app: Flask) -> None:
    """Create the instance and upload folders."""
    upload_path = Path(app.instance_path) / cast(str, app.config["UPLOADS_FOLDER_PATH"])
    if not upload_path.exists():
        upload_path.mkdir(parents=True)
