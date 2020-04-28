from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from pyStocks.__init__ import db, login_manager, app
from flask_login import UserMixin


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    money = db.Column(db.Integer, nullable=False)
    total = db.Column(db.String(60))
    profit = db.Column(db.String(60))
    stocks = db.relationship('UserStocks', backref='owner', lazy=True)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"


class UserStocks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(255))
    shares = db.Column(db.String(255))
    purchase_price = db.Column(db.String(255))
    price = db.Column(db.String(255))
    total_value = db.Column(db.String(255))
    margin = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"UserStocks('{self.symbol}', '{self.shares}, {self.timestamp}', '{self.user_id}')"