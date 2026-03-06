from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask import request, redirect, url_for
import os
from werkzeug.utils import secure_filename
from flask import session
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import cloudinary
import cloudinary.uploader


app = Flask(__name__)


NUMERO_WHATSAPP = "543794256156"
app.permanent_session_lifetime = timedelta(hours=2)

cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

database_url = os.environ.get("DATABASE_URL")

if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:m1a2s3@localhost/catalogo"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#UPLOAD_FOLDER = "static/productos"
#app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.secret_key = os.environ.get("SECRET_KEY", "clave_temporal_dev")

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$rsRqfE2GkJUoSdqj$6c42a633c7a298cb11e67351086801c55b3d33a4648c673528640f09bb5fe543ba785db9be2b6dd56ab10c164a5ce44276aebf1e15dcf5316c32ed5bd9f86c86"

db = SQLAlchemy(app)


# DEFINIR MODELOS PRIMERO
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.String(500), nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Visita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Integer, default=0)


with app.app_context():

    print("Creando tablas...")
    db.create_all()
    print("Tablas creadas correctamente.")


    # crear admin si no existe
    if not User.query.filter_by(username="admin").first():

        admin = User(
            username="admin",
            password_hash=generate_password_hash("12345")
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin creado correctamente")


    # crear contador si no existe
    if not Visita.query.first():

        nueva_visita = Visita(total=0)

        db.session.add(nueva_visita)
        db.session.commit()

        print("Contador creado correctamente")

@app.route("/")
def index():
    productos = Producto.query.all()

    visita = Visita.query.first()

    if visita:
        visita.total += 1
        db.session.commit()
        total_visitas = visita.total
    else:
        total_visitas = 0

    return render_template(
        "index.html",
        productos=productos,
        numero_whatsapp=NUMERO_WHATSAPP,
        visitas=total_visitas,
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio = float(request.form["precio"])

        imagen_file = request.files.get("imagen")

        if not imagen_file:
            flash("Debes subir una imagen", "danger")
            return redirect(url_for("admin"))

        upload_result = cloudinary.uploader.upload(imagen_file)

        imagen_url = upload_result["secure_url"]

        nuevo_producto = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            imagen=imagen_url
        )

        db.session.add(nuevo_producto)
        db.session.commit()
        print("PRODUCTO GUARDADO:", nuevo_producto.id, nuevo_producto.nombre)
        flash("Producto cargado correctamente", "success")

        return redirect(url_for("admin"))

    visita = Visita.query.first()
    total_productos = Producto.query.count()
    productos = Producto.query.order_by(Producto.id.desc()).all()
    
    return render_template(
        "admin.html",
        visitas=visita.total,
        total_productos=total_productos,
        productos=productos,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):

            session['user_id'] = user.id
            session.permanent = True

            flash("Bienvenido al panel de administración", "success")

            return redirect(url_for('admin'))

        else:

            flash("Usuario o contraseña incorrectos", "danger")

            return redirect(url_for('login'))

    return render_template('login.html')


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/eliminar/<int:id>")
def eliminar_producto(id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    producto = Producto.query.get_or_404(id)

    # 2️⃣ Borrar producto de la base
    db.session.delete(producto)
    db.session.commit()

    flash("Producto eliminado correctamente", "danger")

    return redirect(url_for("admin"))


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_producto(id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    producto = Producto.query.get_or_404(id)

    if request.method == "POST":

        producto.nombre = request.form["nombre"]
        producto.descripcion = request.form["descripcion"]
        producto.precio = float(request.form["precio"])

        imagen_file = request.files.get("imagen")

        if imagen_file and imagen_file.filename != "":
            upload_result = cloudinary.uploader.upload(imagen_file)

            producto.imagen = upload_result["secure_url"]
        db.session.commit()
        flash("Producto actualizado correctamente", "info")

        return redirect(url_for("admin"))

    return render_template("editar.html", producto=producto)


@app.route("/cambiar_password", methods=["GET", "POST"])
def cambiar_password():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":

        actual = request.form["actual"]
        nueva = request.form["nueva"]
        confirmar = request.form["confirmar"]

        user = User.query.get(session["user_id"])

        # verificar contraseña actual
        if not check_password_hash(user.password_hash, actual):
            flash("Contraseña actual incorrecta", "danger")
            return redirect(url_for("cambiar_password"))

        # verificar confirmación
        if nueva != confirmar:
            flash("Las contraseñas nuevas no coinciden", "danger")
            return redirect(url_for("cambiar_password"))

        # guardar nueva contraseña
        user.password_hash = generate_password_hash(nueva)
        db.session.commit()

        flash("Contraseña cambiada correctamente", "success")
        return redirect(url_for("admin"))

    return render_template("cambiar_password.html")


@app.template_filter("pesos")
def formato_pesos(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")



   

# SOLO para ejecutar localmente
if __name__ == "__main__":
    app.run(debug=True)
