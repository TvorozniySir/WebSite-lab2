from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Email


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=30)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10)])
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    totp_code = StringField("2FA Code", validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField("Login")


class OrderForm(FlaskForm):
    asset = StringField("Asset", validators=[DataRequired()])
    order_type = SelectField("Type", choices=[("buy", "Buy"), ("sell", "Sell")])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.0001)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0.0001)])
    submit = SubmitField("Place Order")


class BioForm(FlaskForm):
    bio = TextAreaField("О себе (обычный текст)", validators=[Length(max=500)])
    submit = SubmitField("Сохранить")
