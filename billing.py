import time
from datetime import date
from twilio.rest import Client
import sqlite3 as sqlite

conn = sqlite.connect("waterbilling.db")
cur = conn.cursor()
client = Client("ACeedfe773d77c39f6725bc24ffe9531cd","f2702378ff5c895668b3e1bd19f2039e")



while True:

	today = date.today()
	day = today.strftime("%d")
	month = today.strftime("%m")
	year = today.strftime("%Y")


	sql = "SELECT id FROM users"
	cur.execute(sql)
	data = cur.fetchall()

	for i in data:
		sql = "SELECT * FROM billing_info WHERE user_id='{}'".format(i[0])
		cur.execute(sql)
		bills = cur.fetchall()

		check = 0

		for j in bills:
			if int(month) == int(j[3]) and int(year) == int(j[4]):
				check+=1
		if check == 0:
			_id = i[0]
			meter = 10
			amount = int(meter)*10
			sql = "INSERT INTO billing_info(user_id,due_day,due_month,due_year,meter,amount) VALUES('{}','{}','{}','{}','FIX','{}')".format(_id,day,month,year,amount)
			cur.execute(sql)
			conn.commit()

			sql = "SELECT * FROM accounts WHERE id='{}'".format(_id)
			cur.execute(sql)
			data = cur.fetchall()[0]


			sql = "SELECT contact FROM users WHERE id='{}'".format(_id)
			cur.execute(sql)
			user = cur.fetchall()
			contact = user[0][0]
			contact = "+63{}".format(contact[1::])
			_message = "*NOTIFICATION*\nYou have a new bill due on {}-10-{} (MM-DD-YYYY) with an amount of {}.00 PHP\n\nYou can pay your bill on www.waterbilling.com".format(month,year,amount)


			# message = client.messages.create(
			# 	body=_message,
			# 	from_="+13862725541",
			# 	to=contact
			# )
	time.sleep(60)

