from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Initialize Gravatar images for comments
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # Create author_id field from User id
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # References 'posts' attribute in User class
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    # List of blog posts authored by User
    posts = relationship("BlogPost", back_populates="author")
    # List of comments authored by User
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1000), nullable=False)
    comment_author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Reference 'comments' attribute in User class
    comment_author = relationship("User", back_populates="comments")
    parent_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    # Reference 'comments' attribute in BlogPost class
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


# admin_only decorator function
def admin_only(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        # check is user is NOT admin, meaning user is unauthorized - return 403
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return function(*args, **kwargs)
    return wrapper


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    reg_form = RegisterForm()

    # form submitted - create new user in database
    if reg_form.validate_on_submit():
        input_email = reg_form.email.data

        # check if user already exists in database. if yes, redirect to /login
        if User.query.filter_by(email=input_email).first():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))
        hashed_salted_pwd = generate_password_hash(
            reg_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=reg_form.email.data,
            password=hashed_salted_pwd,
            name=reg_form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        # authenticate the new user with Flask-Login
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    # else, render Register form
    return render_template("register.html", form=reg_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    # if user submitted login form
    if login_form.validate_on_submit():
        found_user = User.query.filter_by(email=login_form.email.data).first()

        # check if email is valid
        if not found_user:
            flash("That email does not exist, please try again.")
        # check if password is correct
        elif not check_password_hash(found_user.password, login_form.password.data):
            flash("Incorrect password, please try again.")
        # Valid credentials - log in user with Flask-Login
        else:
            login_user(found_user)
            return redirect(url_for("get_all_posts"))

    # else, render login form
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()

    # new comment submitted
    if comment_form.validate_on_submit():
        # check if user not authenticated
        if not current_user.is_authenticated:
            flash("You need to log in or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment.data,
            comment_author_id=current_user.id,
            comment_author=current_user,
            parent_post_id=post_id,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()

    # else, render post and comment form
    return render_template("post.html", post=requested_post, comment_form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
