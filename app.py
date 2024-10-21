from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///amigo_secreto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
db = SQLAlchemy(app)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    secret_friend = db.Column(db.String(80))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def generate_perfect_match(participants):
    while True:
        shuffled = participants.copy()
        random.shuffle(shuffled)
        if all(a != b for a, b in zip(participants, shuffled)):
            if is_single_cycle(participants, shuffled):
                return list(zip(participants, shuffled))

def is_single_cycle(participants, shuffled):
    cycle = {p: s for p, s in zip(participants, shuffled)}
    visited = set()
    start = participants[0]
    current = start
    while current not in visited:
        visited.add(current)
        current = cycle[current]
        if current == start:
            break
    return len(visited) == len(participants)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        password = request.form.get('password')
        existing_user = Participant.query.filter_by(name=name).first()
        if existing_user:
            flash('Este nome já está em uso. Escolha outro nome.')
        else:
            new_participant = Participant(name=name)
            new_participant.set_password(password)
            if Participant.query.count() == 0:
                new_participant.is_admin = True
            db.session.add(new_participant)
            db.session.commit()
            flash('Participante adicionado com sucesso!')
    return render_template('index.html')

@app.route('/draw')
def draw():
    participants = Participant.query.all()
    if len(participants) < 2:
        flash("Precisa de pelo menos 2 participantes para o sorteio.")
        return redirect(url_for('home'))
    
    names = [p.name for p in participants]
    pairings = generate_perfect_match(names)
    
    for giver, receiver in pairings:
        participant = Participant.query.filter_by(name=giver).first()
        if participant:
            participant.secret_friend = receiver
    
    db.session.commit()
    flash("Sorteio realizado com sucesso!")
    return redirect(url_for('result'))

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/reveal', methods=['POST'])
def reveal():
    name = request.form.get('name')
    password = request.form.get('password')
    participant = Participant.query.filter_by(name=name).first()
    
    if participant and participant.check_password(password):
        return jsonify({"result": participant.secret_friend})
    return jsonify({"error": "Nome ou senha incorretos."}), 400

@app.route('/admin_results', methods=['POST'])
def admin_results():
    name = request.form.get('name')
    password = request.form.get('password')
    admin = Participant.query.filter_by(name=name, is_admin=True).first()
    
    if admin and admin.check_password(password):
        results = {p.name: p.secret_friend for p in Participant.query.all() if p.secret_friend}
        return jsonify(results)
    return jsonify({"error": "Acesso não autorizado"}), 403

@app.route('/reset')
def reset():
    for participant in Participant.query.all():
        participant.secret_friend = None
    db.session.commit()
    flash("Sorteio reiniciado com sucesso!")
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
