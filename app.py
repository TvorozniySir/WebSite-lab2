from flask import (
    Flask, redirect, render_template, render_template_string, request, url_for, abort, flash
)
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from forms import RegisterForm, LoginForm, OrderForm, BioForm
from models import (
    create_user, init_db, get_user_by_username, get_user_by_email,
    get_user_by_id, User, get_connection, get_orders_for_user,
    create_order, get_all_users, mark_email_verified, update_bio,
    get_portfolio_for_user,
)
from email_utils import generate_confirm_token, verify_confirm_token, send_confirmation_email
from auth_jwt import jwt_encode, jwt_decode, JWTError
from functools import wraps
import bcrypt, pyotp, qrcode, io, base64, os, secrets, subprocess

init_db()
app = Flask(__name__)

limiter = Limiter(get_remote_address, app=app)

_secret_key = os.environ.get("FLASK_SECRET_KEY")
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    print("WARNING: FLASK_SECRET_KEY не задан, используется временный ключ")
app.config["SECRET_KEY"] = _secret_key
csrf = CSRFProtect(app)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FORCE_SECURE_COOKIES", "0") == "1",
    PERMANENT_SESSION_LIFETIME=3600,
)


def admin_required(f):
    @wraps(f)
    def decorated_functions(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_functions


def _qr_base64_for(username, totp_secret):
    totp = pyotp.TOTP(totp_secret)
    uri = totp.provisioning_uri(name=username, issuer_name="hackwebapp")
    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@app.route("/")
def home():
    return render_template("base.html")


@app.route("/dashboard")
@login_required
def dashboard():
    bio_html = render_template_string(current_user.bio or "")
    return render_template("dashboard.html", bio_html=bio_html)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = BioForm(obj=current_user)
    if form.validate_on_submit():
        update_bio(current_user.id, form.bio.data)
        flash("Профиль обновлён", "success")
        return redirect(url_for("dashboard"))
    return render_template("profile.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if get_user_by_username(form.username.data):
            flash("Это имя пользователя уже занято", "error")
            return render_template("register.html", form=form)
        if get_user_by_email(form.email.data):
            flash("Этот email уже зарегистрирован", "error")
            return render_template("register.html", form=form)

        create_user(form.username.data, form.email.data, form.password.data)

        token = generate_confirm_token(app.config["SECRET_KEY"], form.email.data)
        send_confirmation_email(request.host_url.rstrip("/"), form.email.data, token)

        flash("Регистрация почти завершена! Проверь консоль сервера — там ссылка для подтверждения email. QR-код для 2FA появится сразу после перехода по ней.", "info")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/confirm/<token>")
def confirm_email(token):
    email = verify_confirm_token(app.config["SECRET_KEY"], token)
    if not email:
        flash("Ссылка подтверждения недействительна или устарела", "error")
        return redirect(url_for("login"))

    user_row = get_user_by_email(email)
    if not user_row:
        flash("Пользователь не найден", "error")
        return redirect(url_for("login"))

    mark_email_verified(email)
    flash("Email подтверждён! Сохрани QR-код и войди.", "success")
    qr_base64 = _qr_base64_for(user_row["username"], user_row["totp_secret"])
    return render_template("qr.html", qr_base64=qr_base64)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_row = get_user_by_username(form.username.data)
        if user_row and bcrypt.checkpw(form.password.data.encode("UTF-8"), user_row["password_hash"]):
            totp = pyotp.TOTP(user_row["totp_secret"])
            if totp.verify(form.totp_code.data):
                if not user_row["email_verified"]:
                    flash("Сначала подтверди email — ссылка была выведена в консоль сервера при регистрации", "error")
                    return render_template("login.html", form=form)
                user = User(user_row)
                login_user(user)
                return redirect(url_for("dashboard"))
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    users = get_all_users()
    return render_template("admin.html", users=users)


@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(user_id)
    if row:
        return User(row)
    return None


@app.route("/order", methods=["GET", "POST"])
@login_required
def order():
    form = OrderForm()
    if form.validate_on_submit():
        ok, error = create_order(
            current_user.id, form.asset.data.upper(),
            form.order_type.data, form.amount.data, form.price.data
        )
        if not ok:
            flash(error, "error")
            return render_template("order.html", form=form)
        flash("Ордер исполнен", "success")
        return redirect(url_for("orders_history"))
    return render_template("order.html", form=form)


@app.route("/orders")
@login_required
def orders_history():
    orders = get_orders_for_user(current_user.id)
    return render_template("orders.html", orders=orders)


@app.route("/portfolio")
@login_required
def portfolio():
    holdings = get_portfolio_for_user(current_user.id)
    return render_template("portfolio.html", holdings=holdings)


@app.route("/api/login", methods=["POST"])
@csrf.exempt
@limiter.limit("10 per minute")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user_row = get_user_by_username(username)
    if user_row and bcrypt.checkpw(password.encode("utf-8"), user_row["password_hash"]):
        token = jwt_encode({
            "user_id": user_row["id"],
            "username": user_row["username"],
            "role": user_row["role"],
        })
        return {"token": token}
    return {"error": "invalid credentials"}, 401


def _bearer_payload():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        return jwt_decode(token)
    except JWTError:
        return None


@app.route("/api/portfolio")
@csrf.exempt
def api_portfolio():
    payload = _bearer_payload()
    if not payload:
        return {"error": "unauthorized"}, 401
    orders = get_orders_for_user(payload["user_id"])
    return {
        "username": payload.get("username"),
        "role": payload.get("role"),
        "orders": [dict(o) for o in orders],
    }


@app.route("/api/admin/users")
@csrf.exempt
def api_admin_users():
    payload = _bearer_payload()
    if not payload:
        return {"error": "unauthorized"}, 401
    if payload.get("role") != "admin":
        return {"error": "forbidden"}, 403
    users = get_all_users()
    return [dict(u) for u in users]


NATIVE_VALIDATOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native", "ticker_validator")


@app.route("/api/validate-ticker", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def api_validate_ticker():
    raw = request.get_data()
    if not raw:
        return {"error": "empty body"}, 400
    if not os.path.exists(NATIVE_VALIDATOR):
        return {"error": "validator not built, run native/build.sh"}, 500
    try:
        proc = subprocess.run([NATIVE_VALIDATOR], input=raw, capture_output=True, timeout=3)
    except subprocess.TimeoutExpired:
        return {"error": "validator timeout"}, 504
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
    }


@app.after_request
def set_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    )
    return resp


DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0") == "1"

if __name__ == "__main__":
    app.run(debug=DEBUG_MODE, host="127.0.0.1", port=5000)
