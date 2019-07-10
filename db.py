from flask import Flask
from flask_admin import Admin
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView

# Create application
app = Flask(__name__)

# Create dummy secrey key so we can use sessions
app.config['SECRET_KEY'] = '123456790'

# Create in-memory database
app.config['DATABASE_FILE'] = 'rhinventory.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE_FILE']
app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app)


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    manufacturer = db.Column(db.String(255))
    model = db.Column(db.String(255))
    nickname = db.Column(db.String(255))
    description = db.Column(db.String(255))
    serial = db.Column(db.String(255))
    image = db.Column(db.String(255))
    status = db.Column(db.Integer)
    condition = db.Column(db.String(255))
    acq_from = db.Column(db.String(255))
    acq_by = db.Column(db.String(255))
    acq_for = db.Column(db.String(255))
    note = db.Column(db.String())


admin = Admin(app)

for table in (Asset, Computer):
    admin.add_view(ModelView(table, db.session))

if __name__ == '__main__':
    app.run(debug=True)
