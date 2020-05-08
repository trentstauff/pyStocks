import os
import secrets
import requests
from PIL import Image
from flask import url_for, flash, redirect
from pyStocks.__init__ import app, db, mail
from pyStocks.models import UserStocks
from flask_login import current_user
from flask_mail import Message
import pyStocks.helpers as helpers
import datetime

global APIKEY
APIKEY = os.environ.get('API_KEY_1')


def purchase_stock(symbol, shares, user):

    status = check_input(symbol, shares)

    if not status:
        return redirect(url_for('home'))

    status = lookup(symbol)

    if not status:
        return redirect(url_for('home'))

    owns_stock = UserStocks.query.filter_by(symbol=symbol, owner=user).all()
    data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=' + APIKEY)
    to_json = data.json()
    current_price = to_json['c']

    stock_to_change = None

    for itr in owns_stock:
        if itr.purchase_price == current_price:
            stock_to_change = itr

    if owns_stock is None or stock_to_change is None:

        total_price = round(current_price * shares, 2)

        if current_user.money < total_price:
            flash(
                'Not enough money! ' + str(symbol) + ' is going for $' + str(current_price) + '. Your cost was $' + str(
                    total_price) + '.', 'danger')
            return redirect(url_for('buy'))

        current_user.money = round(current_user.money - total_price, 2)

        db.session.commit()

        current_price = str(round(current_price, 2))

        stock = UserStocks(shares=shares, symbol=symbol, timestamp=datetime.datetime.now(),
                           price=current_price, purchase_price=current_price, total_value=total_price,
                           owner=current_user)

        db.session.add(stock)

    else:
        amount_purchased = shares
        stock_to_change.shares = stock_to_change.shares + amount_purchased
        stock_to_change.total_value = round(stock_to_change.shares * stock_to_change.price, 2)
        total_price = (round(current_price * shares, 2))

        if current_user.money < total_price:
            flash(
                'Not enough money! ' + str(symbol) + ' is going for $' + str(current_price) + '/share. Your cost was $' + str(
                    total_price) + ', and you only have $' + str(user.money) + '.', 'danger')
            return redirect(url_for('buy'))

        current_user.money = round(current_user.money - total_price, 2)

    db.session.commit()
    refresh()

    if shares == 1:
        flash('Stock purchased: ' + symbol + ' for $' + str(round(total_price, 2)) + '.', 'success')
    else:
        flash('Stocks purchased: ' + symbol + ' x ' + str(shares) + ' for $' + str(round(total_price, 2)) + '.', 'success')
    return True


def sell_stock(symbol, shares, user, stock_id=None):

    status = check_input(symbol, shares)
    if not status:
        return redirect(url_for('home'))

    owns_amount = 0

    if stock_id is None:
        stocklist = UserStocks.query.filter_by(symbol=symbol, owner=user).all()

        for stock in stocklist:
            owns_amount += stock.shares

        if stocklist is None or owns_amount == 0:
            flash('You do not own this stock.', 'warning')
            return redirect(url_for('sell'))
        elif owns_amount < shares:
            flash('You only own ' + str(owns_amount) + ' of ' + symbol + '.', 'warning')
            return redirect(url_for('sell'))

        i = 0
        sell_money = 0
        total_price = 0
        amount_sold = 0

        while i < shares:
            for stock in stocklist:
                while amount_sold < shares:
                    sell_money += stock.price
                    stock.shares = stock.shares - 1
                    amount_sold += 1
                    i = i + 1
                    if stock.shares == 0:
                        db.session.delete(stock)
                        break
            if amount_sold == shares:
                break

        total_price = sell_money
        user.money += sell_money
        user.money = round(user.money, 2)
        db.session.commit()

    else:

        stock = UserStocks.query.filter_by(id=stock_id).first()
        owns_amount = stock.shares

        if stock is None or owns_amount == 0:
            flash('You do not own this stock.', 'warning')
            return redirect(url_for('sell'))
        elif owns_amount < shares:
            flash('You only own ' + str(owns_amount) + ' of ' + symbol + '.', 'warning')
            return redirect(url_for('sell'))

        total_price = stock.price * shares

        updated_balance = current_user.money + total_price
        current_user.money = round(updated_balance, 2)

        stock.shares = owns_amount - shares

        if stock.shares == 0:
            db.session.delete(stock)

        db.session.commit()

    if shares == 1:
        flash('Stock sold: ' + symbol + ' for $' + str(round(total_price, 2)) + '.', 'success')
    else:
        flash('Stocks sold: ' + symbol + ' x ' + shares + ' for $' + str(round(total_price, 2)) + '.', 'success')
    refresh()

    return True


def quote_stock(symbol):

    status = helpers.lookup(symbol)
    if not status:
        return redirect(url_for('home'))

    data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=' + APIKEY)
    to_json = data.json()
    current_price = to_json['c']
    flash(symbol + ' is going for $' + str(round(current_price,2)) + '/share.', 'info')

    return True


def refresh():
    user = current_user
    stock_list = UserStocks.query.filter_by(owner=user).all()
    networth = 0
    profit = 0

    for stock in stock_list:
        symbol = stock.symbol
        data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token='+ APIKEY)
        to_json = data.json()
        current_price = to_json['c']
        stock.margin = round((current_price *stock.shares) - (stock.purchase_price * stock.shares),2)
        stock.price = round(current_price, 2)
        networth += round(stock.total_value, 2)
        profit += stock.margin
        stock.total_value = round(current_price * stock.shares,2)
        db.session.commit()

    user.total = round(networth, 2)
    user.profit = round(profit, 2)
    db.session.commit()

    return redirect(url_for('home'))


def check_input(symbol, shares=None):

    if symbol == '' and shares == '':
        flash('Please give proper values for the Symbol and Shares.', 'warning')
        return False

    if symbol == '':
        flash('Please give a valid ticker for the Symbol.', 'warning')
        return False

    if shares == '':
        flash('Please give a proper value of Shares.', 'warning')
        return False

    if shares is not None and shares < 0:
        flash('Please give a positive value for Shares.', 'warning')
        return False

    return True


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
    the_time = ("%02d:%02d" + setting) % (hours, minutes)

    if weekno > 5:
        flash("It's the weekend, markets are most likely closed. You can still trade, but prices will not change!", 'warning')

    if hours >= 4 and setting == "PM":
        flash("East Coast Markets are closed for the day. They'll open at 9:30 AM (if tomorrow isn't a weekend) ", 'info')

    if hours < 4 and setting == "PM" or hours > 9 and minutes >= 30 and setting == "AM":
        flash("East Coast Markets are open!", 'info')

    flash(the_time + ' EST - East Coast Market Hours: 9:30 AM - 4:00 PM ', 'info')
    return True


def lookup(symbol):
    try:
        data = requests.get('https://finnhub.io/api/v1/quote?symbol=' + symbol + '&token=' + APIKEY)
        info = data.json()
    except:
        flash('Symbol does not exist.', 'danger')
        return False

    return True


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=os.environ.get('EMAIL_USER'),
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
https://trentstauffer.ca/pyStocks/reset_password/{token}
If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    print(picture_path)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn
