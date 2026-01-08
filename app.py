from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)

# Secret key
app.config['SECRET_KEY'] = 'placement-portal-secret'

# Database config (NO manual DB creation)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@app.route('/')
def home():
    return "<h2>Placement Portal Running Successfully ✅</h2>"


if __name__ == '__main__':
    app.run(debug=True)
