from flask import Flask, render_template, request, redirect, url_for, session, Response, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func
from flask_bcrypt import Bcrypt

app=Flask(__name__)

bcrypt = Bcrypt(app)

app.config['SECRET_KEY']='sumit@sharma'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///expense_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False

db=SQLAlchemy(app)

class user(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(100),unique=True,nullable=False)
    password=db.Column(db.String(100),nullable=False)

class Expense_Tracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100))
    amount = db.Column(db.Float)
    category = db.Column(db.String(50))
    date = db.Column(db.Date,nullable=False,default=date.today)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'))

with app.app_context():
    db.create_all()

def date_parser(s:str):
    if not s:
        return None
    try:
        date_str= datetime.strptime(s,"%Y-%m-%d").date()
    except ValueError:
        return None
    return date_str


@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=(request.form.get('username') or "").strip()
        password=(request.form.get('password') or "").strip()
        existing_user = user.query.filter_by(username=username).first()

        if existing_user:
            flash("Username already exists😅")
            return redirect('/register')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = user(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        User=user.query.filter_by(username=username).first()

        if User and bcrypt.check_password_hash(User.password, password):
            session['user_id']=User.id
            return redirect('/')
        
        else:
            flash("Invalid credentials")

    return render_template('login.html')


@app.route('/',methods=['POST','GET'])
def home():
    if 'user_id' not in session:
        return redirect('login')
    
    user_id=session.get('user_id')
    expenses=Expense_Tracker.query.filter_by(user_id=user_id).all()

    start_str=(request.args.get('start') or "").strip()
    end_str=(request.args.get('end') or "").strip()
    category=(request.args.get('category') or "").strip()
    start_date=date_parser(start_str)
    end_date=date_parser(end_str)

    categories=['All','Food','Health','Rent','Utilities','Transport','Others']

    total_expenses = Expense_Tracker.query.filter_by(user_id=user_id).all()
    complete_expense=0
    for e in total_expenses:
        complete_expense+=round(float(e.amount),2)


    if start_date and end_date and end_date<start_date:
        flash("End date cannot be before start date.")
        start_date=end_date=None
        start_str=end_str=""

    q = Expense_Tracker.query.filter_by(user_id=user_id)
    if start_date:
        q=q.filter(Expense_Tracker.date>=start_date)
    if end_date:
        q=q.filter(Expense_Tracker.date<=end_date)
    if category and category!='All':
        q=q.filter(Expense_Tracker.category==category)
    expenses=q.order_by(Expense_Tracker.date.desc(),Expense_Tracker.id.desc()).all()
    total=0
    for e in expenses:
        total=total+round(float(e.amount),2)

    cat_q=db.session.query(Expense_Tracker.category,func.sum(Expense_Tracker.amount)).filter(Expense_Tracker.user_id == user_id)
    if start_date:
        cat_q=cat_q.filter(Expense_Tracker.date >= start_date)
    if end_date:
        cat_q=cat_q.filter(Expense_Tracker.date <= end_date)
    if category and category !='All':
        cat_q=cat_q.filter(Expense_Tracker.category == category)

    cat_row=cat_q.group_by(Expense_Tracker.category).all()
    cat_labels=[c for c,_ in cat_row]
    cat_values_sum=[round(float(s or 0),2) for _,s in cat_row]
    print(cat_labels,cat_values_sum)

    now = datetime.now()

    monthly = db.session.query(func.sum(Expense_Tracker.amount)).filter(
    func.extract('month', Expense_Tracker.date) == now.month,
    func.extract('year', Expense_Tracker.date) == now.year,
    Expense_Tracker.user_id == user_id).scalar()

    top_category = db.session.query(
    Expense_Tracker.category,
    func.sum(Expense_Tracker.amount).label('total')).filter(Expense_Tracker.user_id == user_id).group_by(Expense_Tracker.category).order_by(
    func.sum(Expense_Tracker.amount).desc()).first()

    return render_template("index.html",category=categories,expenses=expenses,today=date.today().isoformat(),start=start_str,end=end_str,total=total,complete_expense=complete_expense,labels=cat_labels,data=cat_values_sum,monthly=monthly,top_category=top_category)

@app.route('/add_expense',methods=["POST"])
def add_expense():
    description=(request.form.get('description') or "").strip()
    amount=(request.form.get('amount') or "").strip()
    category=(request.form.get('category') or "").strip()
    date_str=(request.form.get('date') or "").strip()
    if not description or not amount or not category:
        flash("Please fill the required fields!",'error')
        return redirect(url_for('home'))
    
    try:
        d=datetime.strptime(date_str,"%Y-%m-%d").date() if date_str else date.today()

    except ValueError:
        d=date.today()

    try:
        amount=round(float(amount),2)
        if amount<0:
            raise ValueError
        
    except ValueError:
        flash("Amount must be positive!",'error')
        return redirect(url_for('home'))
    
    added_expense=Expense_Tracker(description=description,amount=amount,category=category,date=d,user_id=session['user_id'] )
    db.session.add(added_expense)
    db.session.commit()

    flash("Expense Added Succesfully",'success')
    return redirect(url_for('home'))

@app.route('/delete_expense/<int:id>',methods=['POST'])
def delete_expense(id):
    e = Expense_Tracker.query.filter_by(id=id,user_id=session['user_id']).first_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted successfully", "success")
    return redirect(url_for('home'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    e = Expense_Tracker.query.get_or_404(id)
    categories = ['Food','Health','Rent','Utilities','Transport','Others']
    return render_template("update.html", e=e, category=categories)

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    e = Expense_Tracker.query.get_or_404(id)
    categories = ['Food','Health','Rent','Utilities','Transport','Others']

    if request.method == 'POST':
        description = (request.form.get('description') or "").strip()
        amount = (request.form.get('amount') or "").strip()
        category = (request.form.get('category') or "").strip()
        date_str = (request.form.get('date') or "").strip()

        if not description or not amount or not category:
            flash("Please fill all required fields!", 'error')
            return render_template("update.html", e=e, category=categories)

        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            d = date.today()

        try:
            amount = round(float(amount), 2)
            if amount < 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number!", 'error')
            return render_template("update.html", e=e, category=categories)

        e.description = description
        e.amount = amount
        e.category = category
        e.date = d

        db.session.commit()

        flash("Expense updated successfully!", 'success')
        return redirect(url_for('home'))
    return render_template("update.html", e=e, category=categories)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)