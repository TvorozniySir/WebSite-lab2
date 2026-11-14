from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

CONFIRM_SALT = "email-confirm"
CONFIRM_MAX_AGE = 3600


def generate_confirm_token(secret_key, email):
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(email, salt=CONFIRM_SALT)


def verify_confirm_token(secret_key, token):
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        email = serializer.loads(token, salt=CONFIRM_SALT, max_age=CONFIRM_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return email


def send_confirmation_email(base_url, email, token):
    confirm_url = f"{base_url}/confirm/{token}"
    print("=" * 60)
    print(f"[EMAIL -> {email}]")
    print(f"Подтвердите регистрацию: {confirm_url}")
    print("=" * 60)
