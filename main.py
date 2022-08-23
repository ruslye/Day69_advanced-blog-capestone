import flask
import flask_login
import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
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

app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config["SECRET_KEY"] = SECRET_KEY
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

gravatar = Gravatar(app,
                    size=100,
                    default="retro",
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)


##CONFIGURE TABLES
#  * To set this up: add the relationship & ForeignKey codes.
#  - Keep the parent db. Delete the existing child db & recreate with create_all.
#  - This will create a new column(author_id) in the child db.

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)

    #  - Setup User class as parent.
    #  - blogs refers to BlogPost attributes. For title in BlogPost, blogs.title; date in BlogPost, blogs.date ...
    blogs = relationship("BlogPost", back_populates="author")  # <-- Parent of BlogPost
    comments = relationship("Comment", back_populates="comment_author")  # <-- Parent of Comment

    def get_id(self):
        return self.id
    @property
    def is_active(self):
        return True
    @property
    def is_authenticated(self):
        return True
    @property
    def is_anonymous(self):
        return False

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    #  - Setup BlogPost class as child.
    #  - author refers to User attributes. For id in User, author.id; name in User, author.name ...
    author = relationship("User", back_populates="blogs")  # <-- child of User

    #  - author_id(new column) references users.id in User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # <-- child's ForeignKey to User

    # author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")  # <-- Parent of Comment


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment_author = relationship("User", back_populates="comments")  # <-- child of User
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # <-- child's ForeignKey to User
    text = db.Column(db.Text, nullable=False)
    parent_post = relationship("BlogPost", back_populates="comments")  # <-- child of BlogPost
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))  # <-- child's ForeignKey to BlogPost


@login_manager.user_loader
def load_user(id):
    return User.query.get(id)

# db.create_all()

def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            abort(403)
        return function(*args, **kwargs)
    return decorated_function


@app.route('/', methods=["GET", "POST"])
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        if User.query.filter_by(email=register_form.email.data).first():
            flash("You have already signed up with that email, log in instead.")
            return redirect("login")
        new_user = User()
        new_user.name = register_form.name.data
        new_user.email = register_form.email.data
        new_user.password = generate_password_hash(register_form.password.data, method='pbkdf2:sha256:1000',
                                                   salt_length=8)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect((url_for("get_all_posts")))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user:
            if check_password_hash(user.password, login_form.password.data):
                login_user(user)
                return redirect((url_for("get_all_posts")))
            flash("Password incorrect, please try again.")
            return redirect("login")
        flash("That email does not exist, please try again.")
        return redirect("login")
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    all_comments = Comment.query.all()
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=comment_form.comment_body.data,
                author_id=current_user.id,
                post_id=post_id,
            )
            db.session.add(new_comment)
            db.session.commit()
            all_comments = Comment.query.all()
            return render_template("post.html", post=requested_post, form=comment_form, all_comments=all_comments)
        flash("You need to login or register to comment.")
        return redirect(url_for("login"))

    return render_template("post.html", post=requested_post, form=comment_form, all_comments=all_comments)


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
    app.run(port=5000, debug=True)
