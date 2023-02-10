def routing():
	if session['log'] == "ADMIN":
		return redirect(url_for("admin"))
	elif session['log'] == "CASHIER":
		return redirect(url_for("cashier"))
	elif session['log'] == "USER":
		return redirect(url_for("user"))

