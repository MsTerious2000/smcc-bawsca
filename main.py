from flask import Flask, render_template, redirect, g, session, url_for, jsonify, request
import sqlite3 as sqlite
from datetime import date
from werkzeug.utils import secure_filename
import os
from twilio.rest import Client
import datetime
# from system import socket, mail
import smtplib
from flask_mail import Mail, Message
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders
import random
import string
import requests

mail = Mail()

date_time = datetime.datetime.now()
client = Client("AC650db9153d59c3403afcd269fcb78312","83cbcb324aeaecf58dc01b71906b9b12")

app = Flask(__name__)
app.secret_key = '/dww213sdd2!@1'
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.before_request
def conn():
    g.conn = sqlite.connect("waterbilling.db")
    g.cur = g.conn.cursor()

def send_sms(number, message):
	payload = {'to':number,'message': message}
	r = requests.post(
	    'http://bawsca.onrender.com/services/api/messaging', params=payload)
	print(r.text)
	return 'Success'

@app.route("/")
def index():
	if "log" not in session:
		return redirect(url_for("login"))
	return redirect(url_for("routing"))

@app.route("/pay_bill/<int:bill_id>", methods=['POST'])
def pay_bill(bill_id):
	file = request.files['reciept']
	filename = secure_filename(file.filename)
	file.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))

	sql = "UPDATE billing_info SET status='GCASH', reciept='{}' WHERE id='{}'".format(filename,bill_id)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("user"))

@app.route("/admin_news")
def admin_news():
	sql = "SELECT n.id, n.message, n.date_posted, n.user_id, a.fname, a.lname, a.account FROM news n JOIN accounts a ON a.id = n.user_id ORDER BY n.date_posted DESC;"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("admin/news.html",data=data)

@app.route("/disconnection")
def disconnection():
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'UNPAID' GROUP BY user_id"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT fname || ' ' || lname AS full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(billing_info.id), due_month, due_day + 5 AS due_day, due_year, SUM(amount) as total_bill, billing_info.status, user_id, max(billing_info.id) as maxid, DATE(due_year || '-' || due_month || '-' || due_day, '5 days') as discon_date FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'FOR DISCONNECTION' ORDER BY billing_info.id DESC"
	g.cur.execute(sql)
	for_disconnection = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("admin/disconnection.html",billing=billing,for_disconnection=for_disconnection,data=session['data'],users=users)

@app.route("/search_disconnection", methods=['POST'])
def search_disconnection():
	search = request.form['user_id']

	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'UNPAID' and (fname LIKE '%{}%' OR lname LIKE '%{}%') GROUP BY user_id".format(search,search)
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT fname || ' ' || lname AS full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(billing_info.id), due_month, due_day + 5 AS due_day, due_year, SUM(amount) as total_bill, billing_info.status, user_id, max(billing_info.id) as maxid FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'FOR DISCONNECTION' and (fname LIKE '%{}%' OR lname LIKE '%{}%') ORDER BY billing_info.id DESC".format(search,search)
	g.cur.execute(sql)
	for_disconnection = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("admin/disconnection.html",billing=billing,for_disconnection=for_disconnection,data=session['data'],users=users)

@app.route("/for_disconnect_user/<int:user_id>")
def for_disconnect_user(user_id):
	sql = '''
			SELECT users.contact, SUM(billing_info.amount) as total, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months FROM users 
			INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.user_id='{}' and status = 'UNPAID';
		'''.format(user_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	sql = "SELECT due_day, due_month, due_year FROM billing_info WHERE user_id = '{}' and status = 'UNPAID' ORDER BY id DESC LIMIT 1".format(user_id)
	g.cur.execute(sql)
	last_bill = g.cur.fetchall()

	sql = "UPDATE billing_info SET status = 'FOR DISCONNECTION' WHERE user_id = '{}' and status = 'UNPAID'".format(user_id)
	g.cur.execute(sql)
	g.conn.commit()
	
	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = '''*NOTIFICATION*\nYour account is scheduled for deactivation on {}-{}-{} with a balance of {}.00 PHP for Billing ID #{}'''.format(last_bill[0][1],int(last_bill[0][0])+5,last_bill[0][2],user[0][1],user[0][2])
	send_sms(contact, _message)
	return redirect(url_for("disconnection"))

@app.route("/disconnect_user/<int:user_id>")
def disconnect_user(user_id):
	sql = '''
			SELECT users.contact, SUM(billing_info.amount) as total, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months FROM users 
			INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.user_id='{}' and status = 'FOR DISCONNECTION';
		'''.format(user_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	sql = "UPDATE billing_info SET status = 'DISCONNECTED' WHERE user_id = '{}' and status = 'FOR DISCONNECTION'".format(user_id)
	g.cur.execute(sql)
	g.conn.commit()
	
	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = '''*NOTIFICATION*\nYour account is deactivated with a balance of {}.00 PHP for Billing ID #{} Please settle your account at our office to continue using our service.'''.format(user[0][1],user[0][2])
	send_sms(contact, _message)
	
	return redirect(url_for("disconnection"))

@app.route("/reconnect_user/<int:user_id>")
def reconnect_user(user_id):
	today = date.today()
	date_today = today.strftime("%m-%d-%Y")

	sql = '''
			SELECT users.contact, SUM(billing_info.amount) as total, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months FROM users 
			INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.user_id='{}' and status = 'DISCONNECTED';
		'''.format(user_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.user_id = '{}' and billing_info.status = 'DISCONNECTED'".format(user_id)
	g.cur.execute(sql)
	recon = g.cur.fetchall()

	sql = "UPDATE billing_info SET status = 'PAID' WHERE user_id = '{}' and status = 'DISCONNECTED'".format(user_id)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "INSERT INTO reconnect_history (user_id, due_dates, amount, number_of_bills, status, reconnection_date) VALUES ('{}', '{}', '{}', '{}', 'RECONNECTED', '{}');".format(recon[0][5], recon[0][1], recon[0][3], recon[0][2], date_today)
	g.cur.execute(sql)
	g.conn.commit()

	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = '''*NOTIFICATION*\nYour account is reconnected. Thank you.'''
	send_sms(contact, _message)
	
	return redirect(url_for("reconnection"))

@app.route("/reconnection")
def reconnection():
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'DISCONNECTED' GROUP BY user_id"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT reconnect_history.*, accounts.fname, accounts.lname FROM reconnect_history JOIN accounts ON reconnect_history.user_id = accounts.id;"
	g.cur.execute(sql)
	recon = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("admin/reconnection.html",billing=billing,data=session['data'],users=users, recon=recon)

@app.route("/search_reconnection", methods=['POST'])
def search_reconnection():
	search = request.form['user_id']
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'DISCONNECTED' and (fname LIKE '%{}%' OR lname LIKE '%{}%') GROUP BY user_id".format(search,search)
	g.cur.execute(sql)
	billing = g.cur.fetchall()
	

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("admin/reconnection.html",billing=billing,data=session['data'],users=users)

@app.route("/news")
def news():
	sql = "SELECT n.id, n.message, n.date_posted, n.user_id, a.fname, a.lname, a.account FROM news n JOIN accounts a ON a.id = n.user_id ORDER BY n.date_posted DESC;"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	sql = "SELECT * FROM billing_info WHERE status = 'DISCONNECTED'".format(session['data'][0])
	g.cur.execute(sql)
	expired = g.cur.fetchall()

	sql = "SELECT *, DATE(due_year || '-' || due_month || '-' || due_day, '5 days') as discon_date FROM billing_info WHERE status = 'FOR DISCONNECTION' AND user_id = '{}' ORDER BY billing_info.id DESC LIMIT 1".format(session['data'][0])
	g.cur.execute(sql)
	for_disconnection = g.cur.fetchall()

	return render_template("user/news.html",data=data, expired=expired,for_disconnection=for_disconnection)

@app.route("/add_news",methods=['POST'])
def add_news():
	today = date_time.strftime("%Y-%m-%d %H:%M:%S")
	news = request.form['news']
	sql = "INSERT INTO news(message,date_posted,user_id) VALUES('{}','{}','{}')".format(news,today,session['data'][0])
	g.cur.execute(sql)
	g.conn.commit()
	if (session['data'][5] == 'CASHIER'):
		return redirect(url_for("cashier"))
	else:
		return redirect(url_for("admin_news"))

@app.route("/edit_news",methods=['POST'])
def edit_news():
	_id = request.form['id']
	today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	news = request.form['news']
	sql = "UPDATE news SET message = '{}', date_posted = '{}' WHERE id = '{}'".format(news,today,_id)
	g.cur.execute(sql)
	g.conn.commit()
	if (session['data'][5] == 'CASHIER'):
		return redirect(url_for("cashier"))
	else:
		return redirect(url_for("admin_news"))

@app.route("/admin")
def admin():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "ADMIN":
		return redirect(url_for("login"))

	sql = '''SELECT  
			(SELECT COUNT(id) FROM `accounts`) AS `users`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` <> 'PAID' and `Status` <> 'DISCONNECTED') AS `pending`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` == 'DISCONNECTED') AS `disconnected`;'''
	g.cur.execute(sql)
	dashboard = g.cur.fetchall()

	sql = '''SELECT * FROM logs;'''
	g.cur.execute(sql)
	logs = g.cur.fetchall()

	return render_template("admin/admin.html",dashboard=dashboard, logs=logs)

# ------------------------------------------- COLLECTOR SIDE ------------------------------------------- #

@app.route("/collector")
def collector():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "COLLECTOR":
		return redirect(url_for("login"))

	sql = '''SELECT  
			(SELECT COUNT(id) FROM `accounts`) AS `users`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` <> 'PAID' and `Status` <> 'DISCONNECTED') AS `pending`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` == 'DISCONNECTED') AS `disconnected`;'''
	g.cur.execute(sql)
	dashboard = g.cur.fetchall()

	sql = "SELECT n.id, n.message, n.date_posted, n.user_id, a.fname, a.lname, a.account FROM news n JOIN accounts a ON a.id = n.user_id ORDER BY n.id DESC;"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("collector/collector.html",dashboard=dashboard, data=data)

@app.route("/collection")
def collection():

	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "COLLECTOR":
		return redirect(url_for("login"))

	# sql = "SELECT * FROM accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id"
	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PICK-UP'"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("collector/collection.html",billing=billing,data=session['data'],users=users)

@app.route("/collection_history")
def collection_history():

	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "COLLECTOR":
		return redirect(url_for("login"))

	# sql = "SELECT * FROM accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id"
	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' AND billing_info.method == 'PICK-UP' AND date_payed IS NOT NULL"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("collector/collection_history.html",billing=billing,data=session['data'],users=users)

# ------------------------------------------- END COLLECTOR SIDE ------------------------------------------- #

# ------------------------------------------- CASHIER SIDE ------------------------------------------- #
@app.route("/search",methods=['POST'])
def search():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "CASHIER":
		return redirect(url_for("login"))

	search = request.form['user_id']
# book_title LIKE '%".$search."%'
	sql = "SELECT * FROM accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id WHERE billing_info.status == 'PAID' and (fname LIKE '%{}%' OR lname LIKE '%{}%') ".format(search, search)
	print(sql)
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()

	return render_template("cashier/search.html",billing=billing,data=session['data'],users=users)

@app.route("/cashier")
def cashier():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "CASHIER":
		return redirect(url_for("login"))

	sql = '''SELECT  
			(SELECT COUNT(id) FROM `accounts`) AS `users`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` <> 'PAID' and `Status` <> 'DISCONNECTED') AS `pending`,
			(SELECT count(id) FROM `billing_info` WHERE `Status` == 'DISCONNECTED') AS `disconnected`;'''
	g.cur.execute(sql)
	dashboard = g.cur.fetchall()

	sql = "SELECT n.id, n.message, n.date_posted, n.user_id, a.fname, a.lname, a.account FROM news n JOIN accounts a ON a.id = n.user_id ORDER BY n.date_posted DESC;"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("cashier/cashier.html",dashboard=dashboard, data=data)

@app.route("/pending")
def pending():

	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "CASHIER":
		return redirect(url_for("login"))

	# sql = "SELECT * FROM accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id"
	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status <> 'PAID'"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("cashier/pending.html",billing=billing,data=session['data'],users=users)

@app.route("/billing_history")
def billing_history():

	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "CASHIER":
		return redirect(url_for("login"))

	sql = "SELECT accounts.*, billing_info.*, users.address, users.consumer_id FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID'"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	year_list = list(range(2021,date_time.year+1))
	return render_template("cashier/billing_history.html",billing=billing,data=session['data'],users=users, year_list=year_list)

@app.route("/search_billing_history", methods=['POST'])
def search_billing_history():
	if "log" not in session:
		return redirect(url_for("login"))

	week = request.form['week']
	month = request.form['month']
	year = request.form['year']
	filter_type = ''
	month_name = ''
	if month == '01':
		month_name = 'January'
	elif month == '02':	
		month_name = 'February'
	elif month == '03':	
		month_name = 'March'
	elif month == '04':	
		month_name = 'April'
	elif month == '05':	
		month_name = 'May'
	elif month == '06':	
		month_name = 'June'
	elif month == '07':	
		month_name = 'July'
	elif month == '08':	
		month_name = 'August'
	elif month == '09':	
		month_name = 'September'
	elif month == '10':	
		month_name = 'October'
	elif month == '11':	
		month_name = 'November'
	else:
		month_name = 'December'

	if (week == '' and month and year):
		filter_type = month_name + ' ' +year
		sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY due_day ASC".format(month, year)
	elif (week == '' and month == '' and year):
		filter_type = year
		sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_year = '{}' ORDER BY due_day ASC".format(year)

	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	year_list = list(range(2021,date_time.year+1))
	if session['log'] == "CASHIER":
		return render_template("cashier/billing_history.html",billing=billing,data=session['data'],users=users, year_list=year_list)

@app.route("/disconnected")
def disconnected():
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id, GROUP_CONCAT(billing_info.id) as billing_ids, date_payed FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'DISCONNECTED' GROUP BY user_id"
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT reconnect_history.*, accounts.fname, accounts.lname FROM reconnect_history JOIN accounts ON reconnect_history.user_id = accounts.id;"
	g.cur.execute(sql)
	recon = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("cashier/disconnected.html",billing=billing,data=session['data'],users=users, recon=recon)

@app.route("/search_disconnected", methods=['POST'])
def search_disconnected():
	search = request.form['user_id']
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id, GROUP_CONCAT(billing_info.id) as billing_ids FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.status = 'DISCONNECTED' and (fname LIKE '%{}%' OR lname LIKE '%{}%') GROUP BY user_id".format(search,search)
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM accounts WHERE account='USER'"
	g.cur.execute(sql)
	users = g.cur.fetchall()
	return render_template("cashier/disconnected.html",billing=billing,data=session['data'],users=users)

@app.route("/walk_in_recon/<billing_ids>/<name>/<amount>/<user_id>",methods=["POST"])
def walk_in_recon(billing_ids,name,amount,user_id):
	billing_id_list = billing_ids.split(",")
	today = date.today()
	date_today = today.strftime("%m-%d-%Y")
	
	sql = "SELECT fname || ' ' || lname as full_name, GROUP_CONCAT(' ' || due_month || '-' || due_year) as months, count(*), SUM(amount) + 50 as total_bill, billing_info.status, user_id FROM billing_info JOIN accounts ON accounts.id = billing_info.user_id WHERE billing_info.user_id = '{}' and billing_info.status = 'DISCONNECTED'".format(user_id)
	g.cur.execute(sql)
	recon = g.cur.fetchall()

	for index, billing_id in enumerate(billing_id_list):
		if index == len(billing_id_list) - 1:
			sql = "UPDATE billing_info SET method='WALK-IN (CASHIER)', date_payed='{}', amount = '150' WHERE id='{}'".format(date_today,billing_id)
		else:
			sql = "UPDATE billing_info SET method='WALK-IN (CASHIER)', date_payed='{}' WHERE id='{}'".format(date_today,billing_id)
		
		g.cur.execute(sql)
		g.conn.commit()

	# log = "CASHIER: {} has confirmed WALK-IN (CASHIER) payment of Bill ID # {} on {}".format(name,billing_id_list,date_today)
	# sql = "INSERT INTO logs(log) VALUES('{}');".format(log)
	# g.cur.execute(sql)
	# g.conn.commit()

	sql = "SELECT users.contact, billing_info.amount FROM users INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.id='{}'".format(billing_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	# sql = "INSERT INTO reconnect_history (user_id, due_dates, amount, number_of_bills, status, reconnection_date) VALUES ('{}', '{}', '{}', '{}', 'RECONNECTED', '{}');".format(recon[0][5], recon[0][1], recon[0][3], recon[0][2], date_today)
	# g.cur.execute(sql)
	# g.conn.commit()

	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nYour Bill of {}.00 PHP for Billing ID #{} has been paid".format(recon[0][3],billing_id)

	send_sms(contact, _message)
	return redirect(url_for("disconnected"))

# ------------------------------------------- END CASHIER SIDE ------------------------------------------- #

# ---------------------------------------------- USER SIDE ---------------------------------------------- #

@app.route("/user")
def user():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "USER":
		return redirect(url_for("login"))

	sql = "SELECT * FROM accounts INNER JOIN users ON accounts.id=users.id WHERE accounts.id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	data = g.cur.fetchall()

	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE user_id='{}' and billing_info.status <> 'PAID' ORDER BY billing_info.id DESC".format(session['data'][0])
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM users WHERE id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	info = g.cur.fetchall()

	sql = "SELECT *, DATE(due_year || '-' || due_month || '-' || due_day, '5 days') as discon_date FROM billing_info WHERE status = 'FOR DISCONNECTION' AND user_id = '{}' ORDER BY billing_info.id DESC LIMIT 1".format(session['data'][0])
	g.cur.execute(sql)
	for_disconnection = g.cur.fetchall()

	sql = "SELECT * FROM billing_info WHERE status = 'DISCONNECTED' AND user_id = '{}'".format(session['data'][0])
	g.cur.execute(sql)
	expired = g.cur.fetchall()

	return render_template("user/user.html",data=data,billing=billing,info=info,expired=expired,for_disconnection=for_disconnection)

@app.route("/user_billing_history")
def user_billing_history():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "USER":
		return redirect(url_for("login"))

	sql = "SELECT * FROM accounts INNER JOIN users ON accounts.id=users.id WHERE accounts.id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	data = g.cur.fetchall()

	sql = "SELECT accounts.*, billing_info.*, users.address, users.consumer_id FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE user_id='{}' and billing_info.status == 'PAID' ORDER BY billing_info.id DESC".format(session['data'][0])
	g.cur.execute(sql)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM users WHERE id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	info = g.cur.fetchall()
	year_list = list(range(2021,date_time.year+1))

	return render_template("user/billing_history.html",data=data,billing=billing,info=info,year_list=year_list)

@app.route("/filter_billing_history", methods=['POST'])
def filter_billing_history():
	if "log" not in session:
		return redirect(url_for("login"))
	elif session['log'] != "USER":
		return redirect(url_for("login"))

	week = request.form['week']
	month = request.form['month']
	year = request.form['year']
	filter_type = ''
	month_name = ''
	if month == '01': month_name = 'January'
	elif month == '02':	month_name = 'February'
	elif month == '03':	month_name = 'March'
	elif month == '04':	month_name = 'April'
	elif month == '05':	month_name = 'May'
	elif month == '06':	month_name = 'June'
	elif month == '07':	month_name = 'July'
	elif month == '08':	month_name = 'August'
	elif month == '09':	month_name = 'September'
	elif month == '10':	month_name = 'October'
	elif month == '11':	month_name = 'November'
	else: month_name = 'December'

	# if (week and month and year):
	# 	filter_type = 'by_all'
	# 	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY due_day ASC".format(month, year)
	if (week == '' and month and year):
		filter_type = month_name + ' ' +year
		bill = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE user_id='{}' and billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY billing_info.id DESC".format(session['data'][0], month, year)
	elif (week == '' and month == '' and year):
		filter_type = year
		bill = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE user_id='{}' and billing_info.status == 'PAID' and due_year = '{}' ORDER BY billing_info.id DESC".format(session['data'][0], year)

	sql = "SELECT * FROM accounts INNER JOIN users ON accounts.id=users.id WHERE accounts.id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	data = g.cur.fetchall()

	g.cur.execute(bill)
	billing = g.cur.fetchall()

	sql = "SELECT * FROM users WHERE id='{}'".format(session['data'][0])
	g.cur.execute(sql)
	info = g.cur.fetchall()
	year_list = list(range(2021,date_time.year+1))

	return render_template("user/billing_history.html",data=data,billing=billing,info=info, year_list=year_list)

@app.route("/user_accounts")
def user_accounts():
	if "log" not in session:
		return redirect(url_for("login"))

	sql = "SELECT accounts.id, accounts.fname, accounts.lname, accounts.username, accounts.account, users.contact, users.email, users.address, users.bday, users.gender, accounts.status FROM accounts INNER JOIN users ON accounts.id=users.id WHERE accounts.account='USER'"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("admin/user_accounts.html",data=data)

@app.route("/pickup_bill/<int:id>", methods=['POST'])
def pickup_bill(id):
	sql = "UPDATE billing_info SET amount = '110', status='PICK-UP' WHERE id='{}'".format(id)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "SELECT user_id FROM billing_info WHERE id = '{}'".format(id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	sql = "SELECT accounts.id, accounts.fname, accounts.lname, users.address FROM accounts JOIN users ON users.id = accounts.id WHERE accounts.id = '{}'".format(user[0][0])
	g.cur.execute(sql)
	user = g.cur.fetchall()

	sql = "SELECT contact FROM employee_info JOIN accounts ON accounts.id = employee_info.id WHERE account = 'COLLECTOR' LIMIT 1"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	contact = data[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nConsumer {} {} request for pickup for their payment at {}".format(user[0][1], user[0][2], user[0][3])

	send_sms(contact, _message)
	return redirect(url_for("user"))

@app.route("/pick_up/<int:bill_id>/<int:user_id>",methods=["POST"])
def pick_up(bill_id, user_id):
	today = date.today()
	date_today = today.strftime("%m-%d-%Y")
	
	sql = "UPDATE billing_info SET status='PAID', method='PICK-UP', amount='110', date_payed='{}' WHERE id='{}'".format(date_today, bill_id)
	g.cur.execute(sql)
	g.conn.commit()
	
	sql = "SELECT email FROM users WHERE id='{}'".format(user_id)
	g.cur.execute(sql)
	data = g.cur.fetchall()

	sql = "SELECT users.contact,billing_info.amount, fname, lname, address, due_month, due_year, method, date_payed FROM users INNER JOIN billing_info ON users.id=billing_info.user_id JOIN accounts ON accounts.id = users.id WHERE billing_info.id='{}'".format(bill_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()
	
	# message = "*NOTIFICATION*\nYour Bill of {}.00 PHP for Billing ID #{} has been paid. Thank you".format(user[0][1],bill_id)
	message = '''
				<html><body>
				<div>
					<div class="text-center" style="font-size: 17px; font-weight: bolder;">
						Barangay Alubihid Water System Consumer's Association <br>
						Address: Barangay Alubihid, Buenavista<br>
						Province: Agusan del Norte<br>
						Phone: <br>

						<h5>Name: {} {}</h5>
						<h5>Address: {}</h5>
						<h5>Classification: Resident</h3>
						<hr>
						<h5>Bill Date: {}/1/{}</h5>
						<h5>Due Date: {}/10/{}</h5>
						<hr>
						Payment Method: <b>{}</b><br>
						Amount Paid: &#8369; {}.00<br>
						Date Paid: {}<br>
					</div>
				</div>
				</body></html>
			'''.format(user[0][2], user[0][3], user[0][4], user[0][5], user[0][6], user[0][5], user[0][6], user[0][7], user[0][1], user[0][8])
	send_email(message, data[0][0])

	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nYour Bill of {}.00 PHP for Billing ID #{} has been payed".format(user[0][1],bill_id)

	send_sms(contact, _message)
	return redirect(url_for("collection"))

@app.route("/profile")
def profile():
	if "log" not in session:
		return redirect(url_for("login"))
	
	sql = "SELECT * FROM accounts WHERE id = '{}'".format(session['data'][0])
	g.cur.execute(sql)
	data = g.cur.fetchall()

	sql = "SELECT * FROM users WHERE id = '{}'".format(session['data'][0])
	g.cur.execute(sql)
	info = g.cur.fetchall()

	return render_template("user/profile.html",info=info,data=data)

@app.route("/forgot_password")
def forgot_password():
	return render_template("forgot-password.html")

@app.route('/reset_password',methods=['POST'])
def reset_password():
	email = request.form['email']
	
	sql = "SELECT email FROM users WHERE email = '{}'".format(email)
	g.cur.execute(sql)
	email = g.cur.fetchall()
	if email:
		random_pass = ''.join(random.choices(string.ascii_lowercase, k=6))
		sql = "UPDATE accounts SET password = '{}' WHERE id = (SELECT id FROM users WHERE email = '{}')".format(random_pass, email[0][0])
		g.cur.execute(sql)
		g.conn.commit()

		message = '''
				<html><body>
				<div>
					<div class="text-center" style="font-size: 17px;">
						Saint Michael College of Caraga <br>
						<p>Good day user this is your new password: <b>{}<b></p>
					</div>
				</div>
				</body></html>
			'''.format(random_pass)
		send_email(message, email[0][0])
		return jsonify({'data': 'success'})
	else:
		return jsonify({'data': 'Invalid email address'})

@app.route("/edit_user_profile", methods=['POST'])
def edit_user_profile():
	_id = session['data'][0]
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	contact = request.form['contact']
	email = request.form['email']
	address = request.form['address'].title()
	bday = request.form['bday']
	gender = request.form['gender'].title()

	sql = "UPDATE accounts SET fname='{}', lname='{}' WHERE id='{}'".format(fname,lname,_id)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "UPDATE users SET contact='{}', email='{}', address='{}', bday='{}', gender='{}' WHERE id='{}'".format(contact,email,address,bday,gender,_id)  
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("profile"))

# ---------------------------------------------- END USER SIDE ---------------------------------------------- #

@app.route("/walk_in/<int:billing_id>/<fname>/<lname>",methods=["POST"])
def walk_in(billing_id,fname,lname):

	today = date.today()
	date_today = today.strftime("%m-%d-%Y")

	sql = "UPDATE billing_info SET status='PAID', method='WALK-IN (CASHIER)', date_payed='{}' WHERE id='{}'".format(date_today,billing_id)
	g.cur.execute(sql)
	g.conn.commit()

	log = "CASHIER: {}, {} has confirmed WALK-IN (CASHIER) payment of Bill ID #{} on {}".format(lname,fname,billing_id,date_today)
	sql = "INSERT INTO logs(log) VALUES('{}')".format(log)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "SELECT users.contact, billing_info.amount FROM users INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.id='{}'".format(billing_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nYour Bill of {}.00 PHP for Billing ID # {} has been paid".format(user[0][1],billing_id)

	send_sms(contact, _message)
	return redirect(url_for("pending"))

@app.route("/verify_gcash/<int:billing_id>/<fname>/<lname>",methods=['POST'])
def verify_gcash(billing_id,fname,lname):

	today = date.today()
	date_today = today.strftime("%m-%d-%Y")

	sql = "UPDATE billing_info SET status='PAID', method='GCash', date_payed='{}' WHERE id='{}'".format(date_today,billing_id)
	g.cur.execute(sql)
	g.conn.commit()

	log = "CASHIER: {}, {} has verified GCash payment of Bill ID #{} on {}".format(lname,fname,billing_id,date_today)
	sql = "INSERT INTO logs(log) VALUES('{}')".format(log)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "SELECT users.contact,billing_info.amount, users.email FROM users INNER JOIN billing_info ON users.id=billing_info.user_id WHERE billing_info.id='{}'".format(billing_id)
	g.cur.execute(sql)
	info = g.cur.fetchall()
	
	contact = info[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nYour GCash payment of {}.00 PHP  has been verified for Billing ID #{}".format(info[0][1],billing_id)

	sql = "SELECT users.contact,billing_info.amount, fname, lname, address, due_month, due_year, method, date_payed FROM users INNER JOIN billing_info ON users.id=billing_info.user_id JOIN accounts ON accounts.id = users.id WHERE billing_info.id='{}'".format(billing_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()

	message = '''
				<html><body>
				<div>
					<div class="text-center" style="font-size: 17px; font-weight: bolder;">
						Barangay Alubihid Water System Consumer's Association <br>
						Address: Barangay Alubihid, Buenavista<br>
						Province: Agusan del Norte<br>
						Phone: <br>

						<h5>Name: {} {}</h5>
						<h5>Address: {}</h5>
						<h5>Classification: Resident</h3>
						<hr>
						<h5>Bill Date: {}/1/{}</h5>
						<h5>Due Date: {}/10/{}</h5>
						<hr>
						Payment Method: <b>{}</b><br>
						Amount Paid: &#8369; {}.00<br>
						Date Paid: {}<br>
					</div>
				</div>
				</body></html>
			'''.format(user[0][2], user[0][3], user[0][4], user[0][5], user[0][6], user[0][5], user[0][6], user[0][7], user[0][1], user[0][8])
	send_email(message, info[0][2])
	send_sms(contact, _message)
	return redirect(url_for("pending"))

@app.route("/submit_reading",methods=['POST'])
def submit_reading():
	_id = request.form['id']
	meter = request.form['meter']

	today = date.today()
	day = today.strftime("%d")
	month = today.strftime("%m")
	year = today.strftime("%Y")
	date_today = today.strftime("%m-%d-%Y")

	amount = int(meter)*10

	sql = "INSERT INTO billing_info(user_id,due_day,due_month,due_year,meter,amount) VALUES('{}','{}','{}','{}','{}','{}')".format(_id,day,month,year,meter,amount)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "SELECT * FROM accounts WHERE id='{}'".format(_id)
	g.cur.execute(sql)
	data = g.cur.fetchall()[0]

	log = "COLLECTOR: {}, {} has submitted Meter Consumption of {}, {} with a Consumtion of {} Cubmic Meter and the Amount of {}php on {}".format(session['data'][2],session['data'][1],data[2],data[1],meter,amount,date_today)
	sql = "INSERT INTO logs(log) VALUES('{}')".format(log)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "SELECT contact FROM users WHERE id='{}'".format(_id)
	g.cur.execute(sql)
	user = g.cur.fetchall()
	contact = user[0][0]
	contact = "+63{}".format(contact[1::])
	_message = "*NOTIFICATION*\nYou have a new bill due on {}-{} (MM-YYYY) with an amount of {}.00 PHP".format(month,year,amount)

	send_sms(contact, _message)
	return redirect(url_for("collector"))

@app.route("/cashier_accounts")
def cashier_accounts():
	if "log" not in session:
		return redirect(url_for("login"))

	sql = "SELECT * FROM accounts WHERE account='CASHIER'"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("admin/cashier_accounts.html",data=data)

@app.route("/collector_accounts")
def collector_accounts():
	if "log" not in session:
		return redirect(url_for("login"))

	sql = "SELECT * FROM accounts JOIN employee_info ON accounts.id = employee_info.id WHERE account='COLLECTOR'"
	g.cur.execute(sql)
	data = g.cur.fetchall()

	return render_template("admin/collector_accounts.html",data=data)

@app.route("/billing_report")
def billing_report():
	if "log" not in session:
		return redirect(url_for("login"))

	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' OR billing_info.status == 'DISCONNECTED' ORDER BY due_day ASC"
	g.cur.execute(sql)
	billing = g.cur.fetchall()
	
	sql = "SELECT * FROM accounts INNER JOIN reconnect_history ON accounts.id = reconnect_history.user_id ORDER BY reconnection_date ASC"
	g.cur.execute(sql)
	recon = g.cur.fetchall()

	sql1 = "SELECT IFNULL(SUM(billing_info.amount), 0) FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' ORDER BY due_day ASC"
	g.cur.execute(sql1)
	total = g.cur.fetchall()

	sql = "SELECT IFNULL(SUM(amount), 0) as total FROM accounts INNER JOIN reconnect_history ON accounts.id = reconnect_history.user_id ORDER BY reconnection_date ASC"
	g.cur.execute(sql)
	total_recon = g.cur.fetchall()

	grand_total = float(total[0][0]) + float(total_recon[0][0])

	year_list = list(range(2021,date_time.year+1))
	if session['log'] == "ADMIN":
		return render_template("admin/billing_report.html",billing=billing,data=session['data'], year_list=year_list, total=grand_total, recon=recon)
	elif session['log'] == "CASHIER":
		return render_template("cashier/billing_report.html",billing=billing,data=session['data'], year_list=year_list, total=grand_total, recon=recon)

@app.route("/search_billing_report", methods=['POST'])
def search_billing_report():
	if "log" not in session:
		return redirect(url_for("login"))

	week = request.form['week']
	month = request.form['month']
	year = request.form['year']
	filter_type = ''
	month_name = ''
	if month == '01':
		month_name = 'January'
	elif month == '02':	
		month_name = 'February'
	elif month == '03':	
		month_name = 'March'
	elif month == '04':	
		month_name = 'April'
	elif month == '05':	
		month_name = 'May'
	elif month == '06':	
		month_name = 'June'
	elif month == '07':	
		month_name = 'July'
	elif month == '08':	
		month_name = 'August'
	elif month == '09':	
		month_name = 'September'
	elif month == '10':	
		month_name = 'October'
	elif month == '11':	
		month_name = 'November'
	else:
		month_name = 'December'

	# if (week and month and year):
	# 	filter_type = 'by_all'
	# 	sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY due_day ASC".format(month, year)
	if (week == '' and month and year):
		filter_type = month_name + ' ' +year
		sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY due_day ASC".format(month, year)
		sql1 = "SELECT IFNULL(SUM(billing_info.amount), 0) FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_month = '{}' and due_year = '{}' ORDER BY due_day ASC".format(month, year)
	elif (week == '' and month == '' and year):
		filter_type = year
		sql = "SELECT accounts.*, billing_info.*, users.address FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_year = '{}' ORDER BY due_day ASC".format(year)
		sql1 = "SELECT  IFNULL(SUM(billing_info.amount), 0) FROM ((accounts INNER JOIN billing_info ON accounts.id=billing_info.user_id) INNER JOIN users on billing_info.user_id=users.id) WHERE billing_info.status == 'PAID' and due_year = '{}' ORDER BY due_day ASC".format(year)

	g.cur.execute(sql)
	billing = g.cur.fetchall()

	g.cur.execute(sql1)
	total = g.cur.fetchall()

	year_list = list(range(2021,date_time.year+1))

	if session['log'] == "ADMIN":
		return render_template("admin/billing_report.html",
								billing=billing,
								data=session['data'], 
								year_list=year_list, 
								filter_type=filter_type,
								total=total[0][0])
	elif session['log'] == "CASHIER":
		return render_template("cashier/billing_report.html",
								billing=billing,
								data=session['data'], 
								year_list=year_list, 
								filter_type=filter_type,
								total=total)

@app.route("/add_user", methods=['POST'])
def add_user():
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	contact = request.form['contact']
	email = request.form['email']
	address = request.form['address'].title()
	bday = request.form['bday']
	gender = request.form['gender'].title()
	account_id = request.form['account_id']

	username = "{}.{}".format(fname.lower(),lname.lower())
	password = "{}{}".format(fname[0].lower(),lname.lower())

	sql = "INSERT INTO accounts(fname,lname,username,password,account,status) VALUES('{}','{}','{}','{}','USER','Active')".format(fname,lname,username,password)
	g.cur.execute(sql)
	g.conn.commit()
	_id = g.cur.lastrowid

	sql = "INSERT INTO users(id,contact,email,address,bday,gender,consumer_id) VALUES('{}','{}','{}','{}','{}','{}','{}')".format(_id,contact,email,address,bday,gender,account_id)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("user_accounts"))

@app.route("/add_cashier", methods=['POST'])
def add_cashier():
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()

	username = "{}.{}".format(fname.lower(),lname.lower())
	password = "{}{}".format(fname[0].lower(),lname.lower())

	sql = "INSERT INTO accounts(fname,lname,username,password,account,status) VALUES('{}','{}','{}','{}','CASHIER','Active')".format(fname,lname,username,password)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("cashier_accounts"))

@app.route("/add_collector", methods=['POST'])
def add_collector():
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	email = request.form['email']
	contact = request.form['contact']

	username = "{}.{}".format(fname.lower(),lname.lower())
	password = "{}{}".format(fname[0].lower(),lname.lower())

	sql = "INSERT INTO accounts(fname,lname,username,password,account,status) VALUES('{}','{}','{}','{}','COLLECTOR', 'Active')".format(fname,lname,username,password)
	g.cur.execute(sql)
	g.conn.commit()
	_id = g.cur.lastrowid

	sql = "INSERT INTO employee_info(id,contact,email) VALUES('{}','{}','{}')".format(_id,email,contact)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("collector_accounts"))

@app.route("/edit_user", methods=['POST'])
def edit_user():
	_id = request.form['id']
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	contact = request.form['contact']
	email = request.form['email']
	address = request.form['address'].title()
	bday = request.form['bday']
	gender = request.form['gender'].title()
	status = request.form['status'].title()

	sql = "UPDATE accounts SET fname='{}', lname='{}', status='{}' WHERE id='{}'".format(fname,lname,status,_id)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "UPDATE users SET contact='{}', email='{}', address='{}', bday='{}', gender='{}' WHERE id='{}'".format(contact,email,address,bday,gender,_id)  
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("user_accounts"))

@app.route("/edit_cashier", methods=['POST'])
def edit_cashier():
	_id = request.form['id']
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	status = request.form['status'].title()
	
	sql = "UPDATE accounts SET fname='{}', lname='{}', status='{}' WHERE id='{}'".format(fname,lname,status,_id)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("cashier_accounts"))

@app.route("/edit_collector", methods=['POST'])
def edit_collector():
	_id = request.form['id']
	fname = request.form['fname'].title()
	lname = request.form['lname'].title()
	status = request.form['status'].title()
	email = request.form['email']
	contact = request.form['contact']
	
	sql = "UPDATE accounts SET fname='{}', lname='{}', status='{}' WHERE id='{}'".format(fname,lname,status,_id)
	g.cur.execute(sql)
	g.conn.commit()

	sql = "UPDATE employee_info SET contact='{}', email='{}' WHERE id='{}'".format(contact,email,_id)
	g.cur.execute(sql)
	g.conn.commit()

	return redirect(url_for("collector_accounts"))

@app.route("/change_password", methods=['POST'])
def change_password():
	_id = session['data'][0]
	old_password = request.form['old_password']
	new_password = request.form['new_password']

	sql = "SELECT * FROM accounts WHERE password='{}'".format(old_password)
	g.cur.execute(sql)
	data = g.cur.fetchall()

	if len(data) == 1:
		print('hi')
		sql = "UPDATE accounts SET password='{}' WHERE id='{}'".format(new_password,_id)
		g.cur.execute(sql)
		g.conn.commit()

		return redirect(url_for("routing"))
	else:
		return "Invalid Old Password"

@app.route("/login")
def login():
	if "log" in session:
		return redirect(url_for("routing"))
	return render_template("login.html")

@app.route("/login_process", methods=['POST'])
def login_process():
	username = request.form['username']
	password = request.form['password']

	sql = "SELECT * FROM accounts WHERE username='{}' and password='{}' and status='Active'".format(username,password)
	g.cur.execute(sql)
	data = g.cur.fetchall()

	if len(data) == 1:
		session['log'] = data[0][5]
		session['data'] = data[0]
		return redirect(url_for("routing"))

	return redirect(url_for("login"))

@app.route("/routing")
def routing():
	if "log" not in session:
		return redirect(url_for("login"))
	if session['log'] == "ADMIN":
		return redirect(url_for("admin"))
	elif session['log'] == "CASHIER":
		return redirect(url_for("cashier"))
	elif session['log'] == "USER":
		return redirect(url_for("news"))
	elif session['log'] == "COLLECTOR":
		return redirect(url_for("collector"))

@app.route("/logout")
def logout():
	session.pop("log",None)
	return redirect(url_for("login"))

def send_email(message, emails):
	email = 'paymentwaterbilling@gmail.com'
	password = 'bqsexwxmovmmmwbi'

	msg = MIMEMultipart()
	msg['From'] = email
	if type(emails) == str:
		msg['To'] = emails
	else:
		msg['To'] = ", ".join(emails)

	msg['Subject'] = 'System Generated Message'
	msg.attach(MIMEText(message, 'html'))

	server = smtplib.SMTP('smtp.gmail.com', 587)
	server.starttls()
	server.login(email, password)
	text = msg.as_string()
	server.sendmail(email, emails, text)
	server.quit()

	return "success"

if __name__ == "__main__":
	app.run(debug=True, host="0.0.0.0")