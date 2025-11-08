"""Provides all routes for the Social Insecurity application.

This file contains the routes for the application. It is imported by the social_insecurity package.
It also contains the SQL queries used for communicating with the database.
"""

from pathlib import Path

from flask import flash, redirect, render_template, url_for, send_from_directory, abort, current_app
from flask import current_app as app
from social_insecurity import sqlite
from social_insecurity.models import User
from social_insecurity.forms import CommentsForm, FriendsForm, IndexForm, PostForm, ProfileForm
from social_insecurity.database import sqlite
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, login_required, current_user, logout_user
from markupsafe import escape


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def index():
    """Provides the index page for the application."""

    index_form = IndexForm()
    login_form = index_form.login
    register_form = index_form.register

    # LOGIN
    if login_form.is_submitted() and login_form.submit.data:
        get_user = "SELECT * FROM Users WHERE username = ?"
        result = sqlite.query(get_user, (login_form.username.data,), one=True)

        user = result if result else None

        if user is None:
            flash("Sorry, this user does not exist!", category="warning")
        elif not check_password_hash(user["password"], login_form.password.data):
            flash("Sorry, wrong password!", category="warning")
        else:
            user_obj = User(
                id=user["id"],
                username=user["username"],
                password=user["password"],
                first_name=user["first_name"] if "first_name" in user.keys() else None,
                last_name=user["last_name"] if "last_name" in user.keys() else None,
            )
            login_user(user_obj)
            flash("Successfully logged in!", category="success")
            return redirect(url_for("stream"))

    # REGISTER
    elif register_form.validate_on_submit():
        insert_user = f"""
            INSERT INTO Users (username, first_name, last_name, password)
            VALUES ('{register_form.username.data}', '{register_form.first_name.data}', '{register_form.last_name.data}', '{generate_password_hash(register_form.password.data)}');
            """
        sqlite.query(insert_user)
        flash("User successfully created!", category="success")
        return redirect(url_for("index"))

    return render_template("index.html.j2", title="Welcome", form=index_form)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/stream", methods=["GET", "POST"])
@login_required
def stream():
    post_form = PostForm()
    user = current_user

    if post_form.validate_on_submit():
        image_filename = None
        if post_form.image.data:
            orig_name = post_form.image.data.filename or ""
            if not allowed_file(orig_name):
                # handle invalid extension - add error and re-render
                post_form.image.errors.append("Invalid image type.")
                return render_template("stream.html.j2", title="Stream", form=post_form, posts=[]) 

            # secure the filename and give it a UUID
            safe_base = secure_filename(orig_name)
            ext = Path(safe_base).suffix or ""
            unique_name = f"{uuid.uuid4().hex}{ext}"

            upload_folder = Path(current_app.instance_path) / current_app.config["UPLOADS_FOLDER_PATH"]
            upload_folder.mkdir(parents=True, exist_ok=True)
            save_path = upload_folder / unique_name

            post_form.image.data.save(save_path)
            image_filename = unique_name

        # escape content before storing (prevents accidental use of |safe later)
        safe_content = escape(post_form.content.data)

        insert_post = """
            INSERT INTO Posts (u_id, content, image, creation_time)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """
        sqlite.query(insert_post, [user.id, safe_content, image_filename])
        return redirect(url_for("stream"))

    # fetch posts
    get_posts = """
         SELECT p.*, u.*, 
                (SELECT COUNT(*) FROM Comments WHERE p_id = p.id) AS cc
         FROM Posts AS p
         JOIN Users AS u ON u.id = p.u_id
         WHERE p.u_id IN (SELECT u_id FROM Friends WHERE f_id = ?)
            OR p.u_id IN (SELECT f_id FROM Friends WHERE u_id = ?)
            OR p.u_id = ?
         ORDER BY p.creation_time DESC
    """
    posts = sqlite.query(get_posts, [user.id, user.id, user.id])
    return render_template("stream.html.j2", title="Stream", form=post_form, posts=posts)


@app.route("/comments/<int:post_id>", methods=["GET", "POST"])
@login_required
def comments(post_id: int):
    """Provides the comments page for the application.

    If a form was submitted, it reads the form data and inserts a new comment into the database.

    Otherwise, it reads the username and post id from the URL and displays all comments for the post.
    """
    comments_form = CommentsForm()
    user = current_user

    if comments_form.is_submitted():
        insert_comment = """
            INSERT INTO Comments (p_id, u_id, comment, creation_time)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP);
        """
        sqlite.query(insert_comment, [post_id, user.id, comments_form.comment.data])

        return redirect(url_for("comments", post_id=post_id))

    get_post = """
        SELECT p.*, u.username
        FROM Posts AS p
        JOIN Users AS u ON p.u_id = u.id
        WHERE p.id = ?
    """

    get_comments = """
        SELECT c.*, u.username
        FROM Comments AS c
        JOIN Users AS u ON c.u_id = u.id
        WHERE c.p_id = ?
        ORDER BY c.creation_time DESC
    """

    post = sqlite.query(get_post, [post_id], one=True)
    comments = sqlite.query(get_comments, [post_id])

    return render_template(
        "comments.html.j2",
        title="Comments",
        form=comments_form,
        post=post,
        comments=comments,
        user=user
    )


@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():
    user = current_user
    friends_form = FriendsForm()

    # Fetch current friends (just IDs) before form handling
    get_friends_ids = """
        SELECT f_id
        FROM Friends
        WHERE u_id = ?;
    """
    friends = sqlite.query(get_friends_ids, [user.id])  # list of sqlite3.Row

    # Handle form submission
    if friends_form.validate_on_submit():
        friend_username = friends_form.username.data.strip()

        get_friend = "SELECT * FROM Users WHERE username = ?;"
        friend = sqlite.query(get_friend, [friend_username], one=True)

        if friend is None:
            flash("User does not exist!", category="warning")
        elif friend["id"] == user.id:
            flash("You cannot be friends with yourself!", category="warning")
        elif friend["id"] in [f["f_id"] for f in friends]:
            flash("You are already friends with this user!", category="warning")
        else:
            insert_friend = "INSERT INTO Friends (u_id, f_id) VALUES (?, ?);"
            sqlite.query(insert_friend, [user.id, friend["id"]])
            flash("Friend successfully added!", category="success")

            # Update friends list after insertion
            friends.append({"f_id": friend["id"]})

    # Fetch full friend info for display
    get_friends_full = """
        SELECT u.*
        FROM Friends AS f
        JOIN Users AS u ON f.f_id = u.id
        WHERE f.u_id = ? AND f.f_id != ?;
    """
    friends_full = sqlite.query(get_friends_full, [user.id, user.id])

    return render_template(
        "friends.html.j2",
        title="Friends",
        friends=friends_full,
        form=friends_form
    )


@app.route("/profile", defaults={"username": None}, methods=["GET", "POST"])
@app.route("/profile/<string:username>", methods=["GET", "POST"])
@login_required
def profile(username):
    """Provides the profile page for the application.

    If a form was submitted, it reads the form data and updates the user's profile in the database.

    Otherwise, it reads the username from the URL and displays the user's profile.
    """
    if username:
        # Look up the user by username in the database
        get_user = "SELECT * FROM Users WHERE username = ?;"
        user = sqlite.query(get_user, [username], one=True)
        if user is None:
            flash("User not found!", "warning")
            return redirect(url_for("profile"))
        user_id = user["id"]
    else:
        # current_user is a Python object
        user = current_user
        user_id = current_user.id

    profile_form = ProfileForm()

    can_edit = (user_id == current_user.id)

    if can_edit and profile_form.validate_on_submit():
        update_profile =  """
            UPDATE Users
            SET education = ?, employment = ?, music = ?, movie = ?, nationality = ?, birthday = ?
            WHERE id = ?;
        """
        sqlite.query(
            update_profile,
            [
                profile_form.education.data,
                profile_form.employment.data,
                profile_form.music.data,
                profile_form.movie.data,
                profile_form.nationality.data,
                profile_form.birthday.data,
                user_id
            ]
        )
        return redirect(url_for("profile", username=username))

    return render_template("profile.html.j2", title="Profile", user=user, form=profile_form, can_edit=can_edit)


@app.route("/uploads/<filename>")
@login_required
def uploads(filename):
    # only serve if filename matches secure_filename (prevents path traversal)
    if secure_filename(filename) != filename:
        abort(404)
    upload_folder = Path(current_app.instance_path) / current_app.config["UPLOADS_FOLDER_PATH"]
    return send_from_directory(upload_folder, filename)