
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime, date, timedelta
from calendar import monthrange

app = Flask(__name__)
app.secret_key = "maharani-subscription-manager-change-this"
DB = "subscriptions.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)

def next_date(d, cycle):
    cycle = cycle.lower()
    if cycle == "monthly":
        return add_months(d, 1)
    if cycle == "quarterly":
        return add_months(d, 3)
    if cycle == "half-yearly":
        return add_months(d, 6)
    if cycle == "yearly":
        return add_months(d, 12)
    return d

def calculated_status(row):
    if row["status"] in ("Cancelled", "Paused", "Trial"):
        return row["status"]
    if row["payment_status"] == "Unpaid":
        due = datetime.strptime(row["renewal_date"], "%Y-%m-%d").date()
        today = date.today()
        delta = (due - today).days
        if delta < 0:
            return "Overdue"
        if delta <= 7:
            return "Due Soon"
    return "Active"

def money(n):
    try:
        n = int(round(float(n)))
    except:
        return "₹0"
    s = str(n)
    if len(s) <= 3:
        return "₹" + s
    last3 = s[-3:]
    rest = s[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return "₹" + ",".join(groups + [last3])

app.jinja_env.filters["money"] = money

def init_db():
    con = get_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'Other',
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        billing_cycle TEXT NOT NULL,
        start_date TEXT,
        renewal_date TEXT NOT NULL,
        payment_status TEXT DEFAULT 'Paid',
        status TEXT DEFAULT 'Active',
        payment_method TEXT DEFAULT '',
        auto_renew INTEGER DEFAULT 1,
        reminder_days INTEGER DEFAULT 7,
        website_url TEXT DEFAULT '',
        account_email TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER,
        subscription_name TEXT,
        amount REAL,
        payment_date TEXT,
        billing_period TEXT,
        payment_method TEXT,
        receipt_no TEXT,
        notes TEXT,
        FOREIGN KEY(subscription_id) REFERENCES subscriptions(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER,
        title TEXT,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    );
    """)
    count = con.execute("SELECT COUNT(*) c FROM subscriptions").fetchone()["c"]
    if count == 0:
        year = date.today().year
        items = [
            ("Claude Pro","AI Tools",2033,"Monthly",f"{year}-08-15","Unpaid","Active","Credit Card",1,7),
            ("Vmake (AI Watermark Remover & Upscaler)","Video Editing",399,"Monthly",f"{year}-08-28","Paid","Active","Credit Card",1,7),
            ("ChatGPT Plus","AI Tools",1999,"Monthly",f"{year}-08-31","Paid","Active","Credit Card",1,7),
            ("Higgsfield AI","AI Tools",5722,"Monthly",f"{year}-09-08","Paid","Active","Credit Card",1,7),
            ("Instagram Blue Tick — Business Max","Social Media",30000,"Monthly",f"{year}-09-11","Paid","Active","Credit Card",1,7),
            ("Adobe Creative Cloud","Design",25980,"Yearly",f"{year+1}-07-04","Paid","Active","Credit Card",1,30),
            ("Canva Pro","Design",4000,"Yearly",f"{year+1}-07-04","Paid","Active","Credit Card",1,30),
            ("Magnific AI","AI Tools",27000,"Yearly",f"{year+1}-08-08","Paid","Active","Credit Card",1,30),
            ("Google AI Pro (Google Flow)","AI Tools",19500,"Yearly",f"{year+1}-08-09","Paid","Active","Credit Card",1,30),
        ]
        for x in items:
            con.execute("""INSERT INTO subscriptions
            (name,category,amount,billing_cycle,renewal_date,payment_status,status,payment_method,auto_renew,reminder_days)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", x)
    con.commit()
    con.close()

def generate_notifications():
    con = get_db()
    subs = con.execute("SELECT * FROM subscriptions WHERE status != 'Cancelled'").fetchall()
    today = date.today()
    for s in subs:
        if s["payment_status"] != "Unpaid":
            continue
        due = datetime.strptime(s["renewal_date"], "%Y-%m-%d").date()
        days = (due - today).days
        title = msg = None
        if days < 0:
            title = f"{s['name']} payment overdue"
            msg = f"{money(s['amount'])} was due on {due.strftime('%d %b %Y')}."
        elif days == 0:
            title = f"{s['name']} payment due today"
            msg = f"{money(s['amount'])} is due today."
        elif days <= (s["reminder_days"] or 7):
            title = f"{s['name']} renewal coming soon"
            msg = f"{money(s['amount'])} is due on {due.strftime('%d %b %Y')}."
        if title:
            exists = con.execute(
                "SELECT id FROM notifications WHERE subscription_id=? AND title=? AND date(created_at)=date('now')",
                (s["id"], title)
            ).fetchone()
            if not exists:
                con.execute("INSERT INTO notifications(subscription_id,title,message) VALUES(?,?,?)",
                            (s["id"], title, msg))
    con.commit()
    con.close()

@app.context_processor
def inject_counts():
    generate_notifications()
    con = get_db()
    unread = con.execute("SELECT COUNT(*) c FROM notifications WHERE is_read=0").fetchone()["c"]
    con.close()
    return {"unread_notifications": unread}

@app.route("/")
def dashboard():
    con = get_db()
    subs = con.execute("SELECT * FROM subscriptions ORDER BY renewal_date").fetchall()
    data = []
    monthly = yearly = overdue_amount = 0
    due_soon = overdue = 0
    for s in subs:
        d = dict(s)
        d["calc_status"] = calculated_status(s)
        data.append(d)
        if d["status"] != "Cancelled":
            if d["billing_cycle"] == "Monthly": monthly += d["amount"]
            if d["billing_cycle"] == "Yearly": yearly += d["amount"]
        if d["calc_status"] == "Due Soon": due_soon += 1
        if d["calc_status"] == "Overdue":
            overdue += 1
            overdue_amount += d["amount"]
    annual_est = monthly * 12 + yearly
    con.close()
    overdue_items = [s for s in data if s["calc_status"] == "Overdue"]
    return render_template("dashboard.html", subs=data, monthly=monthly, yearly=yearly,
                           due_soon=due_soon, overdue=overdue, annual_est=annual_est,
                           overdue_amount=overdue_amount, overdue_items=overdue_items)

@app.route("/subscriptions")
def subscriptions():
    q = request.args.get("q","").strip()
    status = request.args.get("status","").strip()
    cycle = request.args.get("cycle","").strip()
    con = get_db()
    rows = con.execute("SELECT * FROM subscriptions ORDER BY renewal_date").fetchall()
    data=[]
    for s in rows:
        d=dict(s); d["calc_status"]=calculated_status(s)
        if q and q.lower() not in (d["name"]+" "+d["category"]).lower(): continue
        if status and d["calc_status"] != status: continue
        if cycle and d["billing_cycle"] != cycle: continue
        data.append(d)
    overdue_items = [s for s in data if s["calc_status"] == "Overdue"]
    con.close()
    return render_template("subscriptions.html", subs=data, q=q, status=status, cycle=cycle,
                           overdue_items=overdue_items)

@app.route("/subscription/add", methods=["GET","POST"])
def add_subscription():
    if request.method=="POST":
        return save_subscription(None)
    return render_template("form.html", sub=None)

@app.route("/subscription/<int:sid>/edit", methods=["GET","POST"])
def edit_subscription(sid):
    con=get_db()
    sub=con.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
    con.close()
    if not sub:
        flash("Subscription not found.","error")
        return redirect(url_for("subscriptions"))
    if request.method=="POST":
        return save_subscription(sid)
    return render_template("form.html", sub=sub)

def save_subscription(sid):
    name=request.form.get("name","").strip()
    amount=request.form.get("amount","").strip()
    renewal=request.form.get("renewal_date","").strip()
    if not name:
        flash("Subscription name is required.","error")
        return redirect(request.url)
    try:
        amount=float(amount)
    except:
        flash("Please enter a valid amount.","error")
        return redirect(request.url)
    try:
        datetime.strptime(renewal,"%Y-%m-%d")
    except:
        flash("Please enter a valid renewal date.","error")
        return redirect(request.url)
    vals = (
        name,
        request.form.get("category","Other"),
        amount,
        request.form.get("billing_cycle","Monthly"),
        request.form.get("start_date",""),
        renewal,
        request.form.get("payment_status","Paid"),
        request.form.get("status","Active"),
        request.form.get("payment_method",""),
        1 if request.form.get("auto_renew")=="on" else 0,
        int(request.form.get("reminder_days") or 7),
        request.form.get("website_url",""),
        request.form.get("account_email",""),
        request.form.get("notes","")
    )
    con=get_db()
    if sid:
        con.execute("""UPDATE subscriptions SET name=?,category=?,amount=?,billing_cycle=?,start_date=?,
        renewal_date=?,payment_status=?,status=?,payment_method=?,auto_renew=?,reminder_days=?,
        website_url=?,account_email=?,notes=? WHERE id=?""", vals+(sid,))
        flash("Subscription updated successfully.","success")
    else:
        con.execute("""INSERT INTO subscriptions(name,category,amount,billing_cycle,start_date,renewal_date,
        payment_status,status,payment_method,auto_renew,reminder_days,website_url,account_email,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals)
        flash("Subscription added successfully.","success")
    con.commit(); con.close()
    return redirect(url_for("subscriptions"))

@app.post("/subscription/<int:sid>/delete")
def delete_subscription(sid):
    con=get_db()
    con.execute("DELETE FROM subscriptions WHERE id=?", (sid,))
    con.execute("DELETE FROM notifications WHERE subscription_id=?", (sid,))
    con.commit(); con.close()
    flash("Subscription deleted.","success")
    return redirect(request.referrer or url_for("subscriptions"))

@app.post("/subscription/<int:sid>/paid")
def mark_paid(sid):
    con=get_db()
    s=con.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
    if not s:
        con.close(); flash("Subscription not found.","error"); return redirect(url_for("subscriptions"))
    today=date.today()
    due=datetime.strptime(s["renewal_date"],"%Y-%m-%d").date()
    base = max(today, due)
    nxt=next_date(base, s["billing_cycle"])
    con.execute("""INSERT INTO payments(subscription_id,subscription_name,amount,payment_date,billing_period,payment_method,notes)
                   VALUES(?,?,?,?,?,?,?)""",
                (s["id"],s["name"],s["amount"],today.isoformat(),s["billing_cycle"],s["payment_method"],"Marked paid from dashboard"))
    con.execute("UPDATE subscriptions SET payment_status='Paid', renewal_date=? WHERE id=?", (nxt.isoformat(),sid))
    con.execute("DELETE FROM notifications WHERE subscription_id=?", (sid,))
    con.commit(); con.close()
    flash(f"{s['name']} marked as paid. Next renewal: {nxt.strftime('%d %b %Y')}.","success")
    return redirect(request.referrer or url_for("subscriptions"))

@app.post("/subscription/<int:sid>/unpaid")
def mark_unpaid(sid):
    con=get_db()
    con.execute("UPDATE subscriptions SET payment_status='Unpaid' WHERE id=?", (sid,))
    con.commit(); con.close()
    flash("Payment marked as unpaid.","success")
    return redirect(request.referrer or url_for("subscriptions"))

@app.post("/subscription/<int:sid>/cancel")
def cancel(sid):
    con=get_db()
    con.execute("UPDATE subscriptions SET status='Cancelled' WHERE id=?", (sid,))
    con.commit(); con.close()
    flash("Subscription cancelled.","success")
    return redirect(request.referrer or url_for("subscriptions"))

@app.post("/subscription/<int:sid>/reactivate")
def reactivate(sid):
    con=get_db()
    con.execute("UPDATE subscriptions SET status='Active' WHERE id=?", (sid,))
    con.commit(); con.close()
    flash("Subscription reactivated.","success")
    return redirect(request.referrer or url_for("subscriptions"))

@app.route("/due")
def due():
    con=get_db()
    rows=con.execute("SELECT * FROM subscriptions ORDER BY renewal_date").fetchall()
    data=[]
    for s in rows:
        d=dict(s); d["calc_status"]=calculated_status(s)
        if d["calc_status"] in ("Due Soon","Overdue"):
            due_date=datetime.strptime(d["renewal_date"],"%Y-%m-%d").date()
            d["days"]=(due_date-date.today()).days
            data.append(d)
    con.close()
    return render_template("due.html", subs=data)

@app.route("/payments")
def payments():
    con=get_db()
    rows=con.execute("SELECT * FROM payments ORDER BY payment_date DESC,id DESC").fetchall()
    total=con.execute("SELECT COALESCE(SUM(amount),0) t FROM payments").fetchone()["t"]
    con.close()
    return render_template("payments.html", payments=rows, total=total)

@app.route("/notifications")
def notifications():
    con=get_db()
    con.execute("UPDATE notifications SET is_read=1")
    con.commit()
    rows=con.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100").fetchall()
    con.close()
    return render_template("notifications.html", notifications=rows)

@app.route("/calendar")
def calendar_view():
    con=get_db()
    rows=con.execute("SELECT * FROM subscriptions WHERE status != 'Cancelled' ORDER BY renewal_date").fetchall()
    con.close()
    return render_template("calendar.html", subs=rows)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
