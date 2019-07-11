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


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_table = db.Column(db.String(255))
    item_id = db.Column(db.Integer)
    action = db.Column(db.String(255))


class Benchmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    benchmark_run_id = db.Column(db.Integer, db.ForeignKey('benchmark_runs.id'))
    benchmark_type_id = db.Column(db.Integer, db.ForeignKey('benchmark_type.id'))
    computer_id = db.Column(db.Integer, db.ForeignKey('computer.id'))
    rundate = db.Column(db.Integer)  # TODO: transform to DateTime
    runby = db.Column(db.Integer)
    runok = db.Column(db.Integer)
    simpleresult = db.Column(db.Numeric)
    results = db.relationship('BenchmarkResult', backref='benchmark', lazy='dynamic')


class BenchmarkResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.Integer, db.ForeignKey('benchmark.id'))
    mime = db.Column(db.String(255))
    content = db.Column(db.LargeBinary)
    description = db.Column(db.String(4096))
    note = db.Column(db.String(4096))


class BenchmarkRun(db.Model):
    __tablename__ = 'benchmark_runs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    rundate = db.Column(db.DateTime)
    runby = db.Column(db.Integer)  # TODO: link to user
    benchmarks = db.relationship('Benchmark', backref='runs', lazy='dynamic')


class BenchmarkType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    description = db.Column(db.String(4096))
    inputhelp = db.Column(db.String(4096))
    resulthelp = db.Column(db.String(4096))
    benchmarks = db.relationship('Benchmark', backref='bench_type', lazy='dynamic')


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    manufacturer = db.Column(db.String(255))
    model = db.Column(db.String(255))
    nickname = db.Column(db.String(255))
    description = db.Column(db.String(255))
    serial = db.Column(db.String(255))
    image = db.Column(db.String(255))
    status = db.Column(db.Integer, db.ForeignKey('status.id'))
    condition = db.Column(db.String(255))
    acq_from = db.Column(db.String(255))
    acq_by = db.Column(db.String(255))
    acq_for = db.Column(db.String(255))
    note = db.Column(db.String())
    hardware = db.relationship('Hardware', backref='computer', lazy='dynamic')
    benchmarks = db.relationship('Benchmark', backref='computer', lazy='dynamic')
    def __str__(self):
        return "PC{0} {1}".format(str(self.id).zfill(3), self.nickname)

class Hardware(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hardware_type = db.Column(db.Integer, db.ForeignKey('hardware_type.id'))
    computer_id = db.Column(db.Integer, db.ForeignKey('computer.id'))
    name = db.Column(db.String(255))
    manufacturer = db.Column(db.String(255))
    model = db.Column(db.String(255))
    serial = db.Column(db.String(255))
    description = db.Column(db.String(255))
    image = db.Column(db.String(255))
    status = db.Column(db.Integer, db.ForeignKey('status.id'))
    condition = db.Column(db.String(255))
    acq_from = db.Column(db.String(255))
    acq_by = db.Column(db.String(255))
    acq_for = db.Column(db.String(255))
    note = db.Column(db.String())

    def __str__(self):
        return "PK{0} {1}".format(str(self.id).zfill(4), self.name)


class HardwareType(db.Model):
    __tablename__ = 'hardware_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    description = db.Column(db.String(255))
    icon = db.Column(db.String(255))
    items = db.relationship('Hardware', backref='type', lazy='dynamic')

    def __str__(self):
        return self.name


class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))


admin = Admin(app)

for table in (Asset, Benchmark, BenchmarkType, Computer, Hardware):
    admin.add_view(ModelView(table, db.session))

if __name__ == '__main__':
    app.run(debug=True)
