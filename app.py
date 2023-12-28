from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate 

#login and register imports
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
# from flask_wtf import CSRFProtect
# from werkzeug.security import generate_password_hash, check_password_hash

#environment imports
from dotenv import load_dotenv
load_dotenv()

#other imports
import os
from datetime import datetime, time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yourdatabase.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
app.config['SECRET_KEY'] = os.urandom(24)  # Generates a random key

# Initialize Flask-Login
# csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#models

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Goal(db.Model): 
    id = db.Column(db.Integer, primary_key=True)
    target_calories = db.Column(db.Integer, nullable=False)
    target_carbohydrates = db.Column(db.Integer, nullable=False)
    target_protein = db.Column(db.Integer, nullable=False)
    target_fats = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # user_id links a goal to a user

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    calories = db.Column(db.Float, nullable=False)
    carbohydrates = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    fats = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # user_id links a recipe to a user

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)  # e.g., breakfast, lunch, dinner
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # recipe_id and user_id link a meal to a recipe and a user

# routes

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/view_recipe/<int:id>')
@login_required
def view_recipe(id):
    recipe = Recipe.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template('view_recipe.html', recipe=recipe)

@app.route('/view_recipes')
@login_required
def view_recipes():
    user_recipes = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template('view_recipes.html', recipes=user_recipes)

@app.route('/get_meals')
@login_required
def get_meals():
    meals = Meal.query.filter_by(user_id=current_user.id).all()
    goals = Goal.query.filter_by(user_id=current_user.id).first()

    meal_data = []
    daily_totals = {}
    times = {'breakfast': time(7, 0), 'lunch': time(12, 0), 'dinner': time(18, 0)}

    for meal in meals:
        meal_time = times.get(meal.meal_type.lower(), time(0, 0))  # Default to midnight if not matched
        meal_datetime = datetime.combine(meal.date, meal_time)

        total_macros = calculate_total_macros(meal.recipe_id)
        if meal.date not in daily_totals:
            daily_totals[meal.date] = total_macros
        else:
            daily_totals[meal.date]['calories'] += total_macros['calories']
            daily_totals[meal.date]['carbohydrates'] += total_macros['carbohydrates']
            daily_totals[meal.date]['protein'] += total_macros['protein']
        
        if daily_totals[meal.date]['calories'] >= goals.target_calories and daily_totals[meal.date]['carbohydrates'] >= goals.target_carbohydrates and daily_totals[meal.date]['protein'] >= goals.target_protein:
            backgroundColor = 'green'
        else:
            backgroundColor = 'gray'

        meal_data.append({
            'title': meal.meal_type,
            'start': meal_datetime.isoformat(),
            'color': backgroundColor,
            'url': url_for('view_recipe', id=meal.recipe_id)
        })
    return jsonify(meal_data)

def calculate_total_macros(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    return {
        'calories': recipe.calories,
        'carbohydrates': recipe.carbohydrates,
        'protein': recipe.protein
    }

@app.route('/add_recipe', methods=['GET', 'POST'])
@login_required
def add_recipe(): 
    api_key = os.environ.get('CALORIENINJAS_API_KEY')
    if request.method == 'POST':
        # Logic to add a new recipe
        name = request.form['name']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        calories = request.form['calories']
        carbohydrates = request.form['carbohydrates']
        protein = request.form['protein']
        fats = request.form['fats']
        new_recipe = Recipe(name=name, ingredients=ingredients, instructions=instructions, calories=calories, carbohydrates=carbohydrates, protein=protein, fats=fats, user_id=current_user.id)
        db.session.add(new_recipe)
        db.session.commit()
        return redirect(url_for('view_recipes'))
    return render_template('add_recipe.html', api_key=api_key)

@app.route('/plan_meal', methods=['GET', 'POST'])
@login_required
def plan_meal():
    if request.method == 'POST':
        # Logic to plan a new meal
        date = request.form['date']
        meal_type = request.form['meal_type']
        recipe_id = request.form['recipe_id']

        # Convert date string to Python date object
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()

        new_meal = Meal(date=date_obj, meal_type=meal_type, recipe_id=recipe_id, user_id=current_user.id)
        db.session.add(new_meal)
        db.session.commit()
        return redirect(url_for('home'))
    user_recipes = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template('plan_meal.html', recipes=user_recipes)

@app.route('/set_goal', methods=['GET', 'POST'])
@login_required
def set_goal():
    existing_goal = Goal.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        target_calories = request.form['target_calories']
        target_carbohydrates = request.form['target_carbohydrates']
        target_protein = request.form['target_protein']
        target_fats = request.form['target_fats']

        if existing_goal:
            # Update existing goal
            existing_goal.target_calories = target_calories
            existing_goal.target_carbohydrates = target_carbohydrates
            existing_goal.target_protein = target_protein
            existing_goal.target_fats = target_fats
        else:
            # Create new goal
            new_goal = Goal(
                target_calories=target_calories,
                target_carbohydrates=target_carbohydrates,
                target_protein=target_protein,
                target_fats=target_fats,
                user_id=current_user.id
            )
            db.session.add(new_goal)

        db.session.commit()
        return redirect(url_for('set_goal'))

    return render_template('set_goal.html', existing_goal=existing_goal)

#user auth routes

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:  # Replace with secure password check
            login_user(user)
            return redirect(url_for('home'))
        else:
            return render_template('login.html', message='Incorrect username or password. Please try again.')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return render_template('login.html', message='You have been successfully logged out.')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('login.html', message='Username already exists. Please choose a different one.')

        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return render_template('login.html', message='An account with this email already exists. Try logging in or using forgot password.')

        # Hash the password for security
        # hashed_password = generate_password_hash(password)

        # Create a new user and add to the database
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        # Log in the new user
        login_user(new_user)

        return redirect(url_for('home'))

    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)