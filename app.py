import sqlite3
from functools import wraps
from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "troque-esta-chave-em-producao"
DB = "quadras.db"

# recurso -> (tabela, campos editáveis, campos obrigatórios)
RES = {
    "courts": ("courts", ["nome", "modalidade", "preco_hora", "status"], ["nome", "modalidade", "preco_hora"]),
    "users": ("users", ["nome", "email", "perfil"], ["nome", "email"]),
    "tickets": ("tickets", ["assunto", "mensagem", "status"], ["assunto", "mensagem"]),
    "stock": ("stock", ["item", "quantidade", "minimo"], ["item", "quantidade"]),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, nome TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  senha TEXT NOT NULL, perfil TEXT DEFAULT 'cliente');
CREATE TABLE IF NOT EXISTS courts(id INTEGER PRIMARY KEY, nome TEXT NOT NULL, modalidade TEXT NOT NULL,
  preco_hora REAL NOT NULL, status TEXT DEFAULT 'Disponível');
CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, assunto TEXT NOT NULL, mensagem TEXT NOT NULL,
  status TEXT DEFAULT 'Aberto');
CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY, item TEXT NOT NULL, quantidade INTEGER NOT NULL,
  minimo INTEGER DEFAULT 0);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return jsonify(erro="Faça login para continuar."), 401
        return f(*a, **kw)
    return wrapper


def erro(msg, code=400):
    return jsonify(erro=msg), code


@app.route("/")
def index():
    return render_template("index.html")


# ---------- autenticação ----------
@app.post("/api/register")
def register():
    d = request.get_json(force=True)
    nome, email, senha = (d.get(k, "").strip() for k in ("nome", "email", "senha"))
    if not nome or not email or len(senha) < 4:
        return erro("Preencha nome, e-mail e uma senha com 4+ caracteres.")
    first = db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    try:
        db().execute("INSERT INTO users(nome,email,senha,perfil) VALUES(?,?,?,?)",
                     (nome, email, generate_password_hash(senha), "admin" if first else "cliente"))
        db().commit()
    except sqlite3.IntegrityError:
        return erro("Este e-mail já está cadastrado.")
    return jsonify(ok=True), 201


@app.post("/api/login")
def login():
    d = request.get_json(force=True)
    u = db().execute("SELECT * FROM users WHERE email=?", (d.get("email", "").strip(),)).fetchone()
    if not u or not check_password_hash(u["senha"], d.get("senha", "")):
        return erro("E-mail ou senha incorretos.", 401)
    session["uid"] = u["id"]
    return jsonify(id=u["id"], nome=u["nome"], perfil=u["perfil"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if "uid" not in session:
        return jsonify(logado=False)
    u = db().execute("SELECT id,nome,perfil FROM users WHERE id=?", (session["uid"],)).fetchone()
    return jsonify(logado=True, **dict(u)) if u else jsonify(logado=False)


# ---------- CRUD genérico ----------
def parse(res, partial=False):
    _, fields, required = RES[res]
    d = request.get_json(force=True)
    data = {f: d[f] for f in fields if f in d and str(d[f]).strip() != ""}
    for f in required:
        if f not in data:
            return None, f"Campo obrigatório: {f}"
    try:
        for f in ("preco_hora",):
            if f in data: data[f] = float(data[f])
        for f in ("quantidade", "minimo"):
            if f in data: data[f] = int(data[f])
    except ValueError:
        return None, "Valor numérico inválido."
    return data, None


@app.get("/api/<res>")
@login_required
def listar(res):
    if res not in RES: return erro("Recurso inválido.", 404)
    cols = ",".join(["id"] + RES[res][1])
    rows = db().execute(f"SELECT {cols} FROM {RES[res][0]} ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/<res>")
@login_required
def criar(res):
    if res not in RES or res == "users": return erro("Operação inválida.", 404)
    data, err = parse(res)
    if err: return erro(err)
    ks = ",".join(data)
    db().execute(f"INSERT INTO {RES[res][0]}({ks}) VALUES({','.join('?' * len(data))})", list(data.values()))
    db().commit()
    return jsonify(ok=True), 201


@app.put("/api/<res>/<int:rid>")
@login_required
def atualizar(res, rid):
    if res not in RES: return erro("Recurso inválido.", 404)
    data, err = parse(res)
    if err: return erro(err)
    sets = ",".join(f"{k}=?" for k in data)
    try:
        db().execute(f"UPDATE {RES[res][0]} SET {sets} WHERE id=?", [*data.values(), rid])
        db().commit()
    except sqlite3.IntegrityError:
        return erro("E-mail já em uso.")
    return jsonify(ok=True)


@app.delete("/api/<res>/<int:rid>")
@login_required
def apagar(res, rid):
    if res not in RES: return erro("Recurso inválido.", 404)
    db().execute(f"DELETE FROM {RES[res][0]} WHERE id=?", (rid,))
    db().commit()
    return jsonify(ok=True)


with sqlite3.connect(DB) as c:
    c.executescript(SCHEMA)

if __name__ == "__main__":
    app.run(debug=True)
