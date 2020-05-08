import os
from flask import render_template, url_for, flash, redirect, request
from pyStocks.__init__ import app, db, bcrypt
from pyStocks.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             RequestResetForm, ResetPasswordForm, BuyForm, SellForm)
from pyStocks.models import User, UserStocks
from flask_login import login_user, current_user, logout_user, login_required
from pyStocks.stocks import stocks as stock_list
import pyStocks.helpers as helpers

global APIKEY
APIKEY = os.environ.get('API_KEY_1')


# the home route is where the user's portfolio is displayed
@login_required
@app.route("/pyStocks/home")
def home():
 
    user = current_user
    stocks = UserStocks.query.filter_by(owner=user).order_by(UserStocks.symbol).all()
    user.stocks = stocks
    helpers.check_day()

    return render_template('home.html', user=user)


# the home route is where the user can go to see information about pyStocks and how to use it
@app.route("/pyStocks/about")
def about():
    return render_template('about.html', title='About')


# registration page
@app.route("/pyStocks/register", methods=['GET', 'POST'])
def register():

    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegistrationForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        rounded_money = round(form.money.data, 2)
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, money=rounded_money)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', form=form)


# login page
@app.route("/pyStocks/", methods=['GET', 'POST'])
@app.route("/pyStocks/login", methods=['GET', 'POST'])
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


# logout page
@app.route("/pyStocks/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))


# this route is for the user if they would like to update info about their account
@app.route("/pyStocks/account", methods=['GET', 'POST'])
@login_required
def account():

    form = UpdateAccountForm()

    if form.validate_on_submit():
        if form.picture.data:
            picture_file = helpers.save_picture(form.picture.data)
            current_user.image_file = picture_file

        if form.money.data:
            current_user.money = round(form.money.data,2)

        current_user.username = form.username.data
        current_user.email = form.email.data

        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))

    # this is for the html to auto place the users current information
    elif request.method == 'GET':

        form.username.data = current_user.username
        form.email.data = current_user.email
        form.money.data = current_user.money

    image_file = '/static/profile_pics/' + current_user.image_file
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


@app.route("/pyStocks/leaderboard")
def leaderboard():
    user = current_user
    users = User.query.filter(User.profit != None).order_by(User.profit.desc()).all()

    return render_template('leaderboard.html', user=user, users=users)


# this route deals with buying stocks. Either from /buy, or from the form on the users portfolio
@app.route('/pyStocks/buy', methods=['GET', 'POST'])
@app.route('/pyStocks/buy/<string:stock_id>', methods=['GET', 'POST'])
@login_required
def buy(stock_id=None):

    user = current_user

    # if stock_id is passed, this means the user clicked buy on an individual stock that is already in their portfolio
    if stock_id is not None:
        stock = UserStocks.query.filter_by(id=stock_id).first()
        helpers.purchase_stock(stock.symbol, 1, user)
        return redirect(url_for('home'))

    # this deals with the form to buy stocks, so no id is passed
    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')
        passed_shares = int(request.form.get('shares'))

        status = helpers.check_input(passed_symbol, passed_shares)

        if status is False:
            return redirect(url_for('home'))

        # this check is to not only limit purchases to reasonable values, but to prevent overflow with MAX_INTEGER in python
        # this is a safety check to prohibit injection into the server if MAX_INTEGER is overflowed as well.
        if float(passed_shares) > 100000:
            flash("Max shares per sale is 100,000.", 'warning')
            return redirect(url_for('home'))

        if passed_shares is None:
            passed_shares = 1

        helpers.purchase_stock(passed_symbol, passed_shares, user)
        return redirect(url_for('home'))
    else:
        # this else clause deals with the endpoint /buy, a legacy feature
        form = BuyForm()

        if form.validate_on_submit():
            helpers.purchase_stock(form.symbol.data, form.shares.data, user)

    return render_template('buy_container.html', title='Buy', form=form, stocks=stock_list)


# this route deals with selling stocks. Either from /sell, or from the form on the users portfolio
@app.route('/pyStocks/sell', methods=['GET', 'POST'])
@app.route('/pyStocks/sell/<string:stock_id>', methods=['GET', 'POST'])
@login_required
def sell(stock_id=None):

    # this function follows the buy function, but with selling instead of buying

    user = current_user

    if stock_id is not None:
        stock = UserStocks.query.filter_by(id=stock_id).first()
        helpers.sell_stock(stock.symbol, 1, user, stock_id)
        return redirect(url_for('home'))

    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')
        passed_shares = int(request.form.get('shares'))

        status = helpers.check_input(passed_symbol, passed_shares)

        if status is False:
            return redirect(url_for('home'))

        if float(passed_shares) > 100000:
            flash("Max shares per sale is 100,000.", 'warning')
            return redirect(url_for('home'))

        helpers.sell_stock(passed_symbol, passed_shares, user)
        return redirect(url_for('home'))
    else:

        form = SellForm()

        if form.validate_on_submit():
            helpers.sell_stock(form.symbol.data, form.shares.data, user)

    return render_template('sell.html', title='Sell', form=form)


# this route is a quick way for the user to get the current price/share of a stock
@app.route('/pyStocks/quote', methods=['GET', 'POST'])
@login_required
def quote():

    user = current_user

    if request.method == 'POST':
        passed_symbol = request.form.get('symbol')

        status = helpers.check_input(passed_symbol)

        if status is False:
            return redirect(url_for('home'))

        helpers.quote_stock(passed_symbol)
        return redirect(url_for('home'))


# this route is used by the "Refresh Button"
# in helpers.py, you'll see that prices refresh whenever a user executes an action,
# and not just when they press the button.
@app.route('/pyStocks/refresh', methods=['GET', 'POST'])
@login_required
def refresh():
    helpers.refresh()
    return redirect(url_for('home'))


# this route will delete all of the user's stocks from the database
@app.route("/pyStocks/clearportfolio/<int:user_id>", methods=['GET', 'POST'])
@login_required
def clear_portfolio(user_id):

    user = User.query.get(user_id)

    if user != current_user:
        flash('You can only delete your own portfolio!', 'danger')
        return redirect('pyStocks/'+url_for('home'))

    user.total = 0
    user.profit = 0

    stocks = UserStocks.query.filter_by(owner=user).all()

    for stock in stocks:
        db.session.delete(stock)

    user.money = 10000

    db.session.commit()
    flash(
        "Your portfolio has been cleared. Your balance has been set to $10,000. You can change this in your Account page.",
        'success')
    return redirect(url_for('home'))


# this route allows for users to reset their password by clicking a button on the login page
@app.route('/pyStocks/reset_password', methods=['GET', 'POST'])
def reset_request():

    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RequestResetForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        helpers.send_reset_email(user)
        flash("An email has been sent with instructions to reset your password.", 'info')
        return redirect(url_for('login'))

    return render_template('reset_request.html', title='Reset Password', form=form)


# this route deals with the token the user gives from the emailed link, and checks to see if it is valid to the user
@app.route('/pyStocks/reset_password/<token>', methods=['GET', 'POST'])
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