import os
import secrets
import requests
import time
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, session
from pyStocks.__init__ import app, db, bcrypt, mail
from pyStocks.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             RequestResetForm, ResetPasswordForm, BuyForm, SellForm)
from pyStocks.models import User, UserStocks
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
import datetime
from decimal import Decimal
from pytz import timezone


# bqhk5snrh5rdcs9r2i30

@login_required
@app.route("/home")
def home():
    user = current_user;
    check_day()
    return render_template('home.html', user=user)


@app.route('/buy', methods=['GET', 'POST'])
@app.route('/buy/<string:stock_id>', methods=['GET', 'POST'])
@login_required
def buy(stock_id=None):
    user = current_user

    if stock_id is not None:
        stock = UserStocks.query.filter_by(id=stock_id).first()
        purchase_stock(stock.symbol, 1, user)
        return redirect(url_for('home'))

    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')
        passed_shares = request.form.get('shares')
        if passed_shares is None:
            passed_shares = 1
        purchase_stock(passed_symbol, passed_shares, user)
        return redirect(url_for('home'))
    else:
        form = BuyForm()

    # check to see if ticker is a symbol
    #
    #
    #
    #
        if form.validate_on_submit():
            purchase_stock(form.symbol.data, form.shares.data, user)

    return render_template('buy.html', title='Buy', form=form)


def purchase_stock(symbol, shares, user):

    status = check_input(symbol, shares)
    if status == -1:
        return redirect(url_for('home'))

    status = lookup(symbol)
    if status == -1:
        return redirect(url_for('home'))

    owns_stock = UserStocks.query.filter_by(symbol=symbol, owner=user).first()
    data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=bqhk5snrh5rdcs9r2i30')
    to_json = data.json()
    current_price = to_json['c']

    if owns_stock is None or float(current_price) != float(owns_stock.price):

        total_price = float(round(Decimal(current_price * float(shares)), 2))

        if current_user.money < total_price:
            flash(
                'Not enough money! ' + str(symbol) + ' is going for $' + str(current_price) + '. Your cost was $' + str(
                    total_price) + '.', 'danger')
            return redirect(url_for('buy'))

        current_user.money = round(float(Decimal(current_user.money - total_price)), 2)
        db.session.commit()

        stock = UserStocks(shares=shares, symbol=symbol, timestamp=datetime.datetime.now(),
                           price=current_price, purchase_price=current_price, total_value=total_price,
                           owner=current_user)
        db.session.add(stock)
    else:
        amount_purchased = int(shares)
        owns_stock.shares = str(int(owns_stock.shares) + amount_purchased)
        owns_stock.total_value = str(round((float(owns_stock.shares) * float(owns_stock.price)),2))
        total_price = float(round(Decimal(current_price * float(shares)), 2))

        if current_user.money < total_price:
            flash(
                'Not enough money! ' + str(symbol) + ' is going for $' + str(current_price) + '/share. Your cost was $' + str(
                    total_price) + ', and you only have $' + str(user.money) + '.', 'danger')
            return redirect(url_for('buy'))
        current_user.money = round(float(Decimal(current_user.money - total_price)), 2)

    db.session.commit()
    refresh()
    if int(shares) == 1:
        if owns_stock is None:
            flash('Stock purchased: ' + symbol + ' for $' + str(
                round(total_price, 2)) + '.', 'success')
            return 1
        flash('Stock purchased: ' + symbol + ' for $' + str(round(total_price, 2)) + '. You now own ' + owns_stock.shares + '.', 'success')
    else:
        if owns_stock is None:
            flash('Stock purchased: ' + symbol + ' for $' + str(
                round(total_price, 2)) + '.', 'success')
            return 1
        flash('Stocks purchased: ' + symbol + ' x ' + shares + ' for $' + str(round(total_price, 2)) + '. You now own ' + owns_stock.shares + '.', 'success')
    return 1


@app.route('/sell', methods=['GET', 'POST'])
@app.route('/sell/<string:stock_id>', methods=['GET', 'POST'])
@login_required
def sell(stock_id=None):
    user = current_user

    if stock_id is not None:
        stock = UserStocks.query.filter_by(id=stock_id).first()
        sell_stock(stock.symbol, 1, user)
        return redirect(url_for('home'))

    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')
        passed_shares = request.form.get('shares')
        sell_stock(passed_symbol, passed_shares, user)
        return redirect(url_for('home'))
    else:

        form = SellForm()

        if form.validate_on_submit():
            sell_stock(form.symbol.data, form.shares.data, user)

    return render_template('sell.html', title='Sell', form=form)


def sell_stock(symbol, shares, user):

    status = check_input(symbol, shares)
    if status == -1:
        return redirect(url_for('home'))

    stock = UserStocks.query.filter_by(symbol=symbol, owner=user).first()

    if stock is None:
        flash('You do not own this stock.', 'warning')
        return redirect(url_for('sell'))

    owns_amount = stock.shares
    if float(owns_amount) == 0:
        flash("You don't own any stocks of " + symbol + ' .', 'warning')
        return redirect(url_for('sell'))
    elif float(owns_amount) < float(shares):
        flash('You only own ' + str(owns_amount) + ' of ' + symbol + '.', 'warning')
        return redirect(url_for('sell'))

    total_price = float(stock.purchase_price) * float(shares)

    updated_balance = Decimal(current_user.money + total_price)
    current_user.money = float(round(updated_balance, 2))

    stock.shares = int(owns_amount) - int(shares)

    if stock.shares == 0:
        db.session.delete(stock)

    db.session.commit()

    if shares == 1:
        flash('Stock sold: ' + symbol + ' for $' + str(round(total_price, 2)) + '.', 'success')
    else:
        flash('Stocks sold: ' + symbol + ' x ' + shares + ' for $' + str(round(total_price, 2)) + '.', 'success')
    refresh()
    return 1


def check_input(symbol, shares):

    if symbol == '' and shares == '':
        flash('Please give proper values for the Symbol and Shares.', 'warning')
        return -1

    if symbol == '':
        flash('Please give a valid ticker for the Symbol.', 'warning')
        return -1

    if shares == '':
        flash('Please give a proper value of Shares.', 'warning')
        return -1

    return 1


@app.route('/quote', methods=['GET', 'POST'])
@login_required
def quote():

    user = current_user
    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')
        quote_stock(passed_symbol)
        return redirect(url_for('home'))


def quote_stock(symbol):

    status = lookup(symbol)
    if status == -1:
        return redirect(url_for('home'))

    data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=bqhk5snrh5rdcs9r2i30')
    to_json = data.json()
    current_price = to_json['c']
    flash(symbol + ' is going for $' + str(current_price) + '/share.', 'info')
    return 1


@app.route('/refresh', methods=['GET', 'POST'])
@login_required
def refresh():
    user = current_user
    stock_list = UserStocks.query.filter_by(owner=user).all()
    networth = 0
    profit = 0
    for stock in stock_list:
        symbol = stock.symbol
        data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=bqhk5snrh5rdcs9r2i30')
        to_json = data.json()
        current_price = to_json['c']
        stock.margin = str(round((float(stock.purchase_price) * float(stock.shares)) - (current_price * float(stock.shares)),2))
        stock.current_price = current_price
        networth += round(Decimal(float(stock.total_value)), 2)
        profit += float(stock.margin)

    user.total = str(networth)
    db.session.commit()

    return redirect(url_for('home'))


def check_day():
    weekno = datetime.datetime.today().weekday()
    data = datetime.datetime.now()
    current_time = data.strftime("%H:%M")

    hours, minutes = current_time.split(":")
    hours, minutes = int(hours), int(minutes)
    setting = "AM"
    if hours > 12:
        setting = "PM"
        hours -= 12
    time = ("%02d:%02d" + setting) % (hours, minutes)

    if weekno > 5:
        flash("It's the weekend, markets are most likely closed. You can still trade, but prices will not change!", 'warning')
    return 1

    if hours >= 5 and setting == "PM":
        flash("East coast markets are closed for the day. They'll open at 9:30 AM (if tomorrow isn't a weekend) ", 'info')

    if hours < 5 and setting == "PM" or hours > 9 and minutes >= 30 and setting == "AM":
        flash("East coast markets are open! Hours: 9:30 AM - 5:00 PM ", 'info')

    flash(time + ' EST', 'info')
    return 1

def lookup(symbol):
    try:
        data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=bqhk5snrh5rdcs9r2i30')
        info = data.json()
    except:
        flash('Symbol does not exist.', 'danger')
        return -1

    return 1



@app.route("/clearportfolio/<int:user_id>", methods=['GET', 'POST'])
def clear_portfolio(user_id):
    user = User.query.get(user_id)
    if user != current_user:
        flash('You can only delete your own portfolio!', 'danger')
        return redirect(url_for('home'))

    user.total = 0;
    user.profit = 0;

    stocks = UserStocks.query.filter_by(owner=user).all()

    for stock in stocks:
        db.session.delete(stock)

    db.session.commit()
    flash("Your portfolio has been cleared.", 'success')
    return redirect(url_for('home'))


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, money=form.money.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/", methods=['GET', 'POST'])
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        if form.money.data:
            current_user.money = form.money.data
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash("An email has been sent with instructions to reset your password.", 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    # compares the token to tokes that this user holds
    # we made this function in models.py User class
    # this returns the user id
    user = User.verify_reset_token(token)
    if user is None:
        flash("That token isn't valid, or has expired.", 'warning')
        return redirect(url_for('reset_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been changed. You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)