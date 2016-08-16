# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, jsonify, flash, session
from flask_assets import Environment, Bundle
import secret
from jinja2 import StrictUndefined
from datetime import datetime

from model import connect_to_db, db, Plant, User

app = Flask(__name__)
assets = Environment(app)
app.secret_key = secret.APP_KEY

app.jinja_env.undefined = StrictUndefined

# ************************* ASSETS *********************************
assets.url = app.static_url_path

scss = Bundle('css/sass.scss', filters='pyscss', output='css/style.css')
assets.register('scss_all', scss)

css = Bundle('css/sweetalert.css')
assets.register('css_all', css)

js = Bundle('js/app.js', 'js/sweetalert.min.js')
assets.register('js_all', js)


# ************************* ROUTES *********************************

# Basic Routes *********************************


@app.route('/')
def index_page():
    """Show index page."""

    return render_template("index.html")


@app.route('/search', methods=['GET'])
def search_for_plant():
    """Displays search results."""

    # gets the user's search term from app.js and queries the db
    search_term = request.args.get('plant-name')
    results = Plant.query.filter(Plant.name.ilike('%' + search_term + '%')).all()

    if len(results) > 0:
        plants_found = {}

        # for each plant in the results, make dictionary using plant's id as key
        # and plant's name as value
        for plant in results:
            plants_found[plant.plant_id] = plant.name

        return jsonify(plants_found)
    else:
        return 'None'


# User Routes *********************************

@app.route('/login')
def login_form():
    """Renders login form"""
    return render_template('login_form.html')


@app.route('/process_login', methods=['POST'])
def process_login():
    """Processes user input and either logs user in if input is in database"""

    # gets the user input from the username field and looks it up in the database
    username = request.form.get('username')
    user = User.query.filter_by(username=username).first()

    # if username entered exists in db, gets the password entered and compares
    # it to the one in the database
    if user:
        password = request.form.get('password')
        # if password is correct, adds user to the current session and redirects to home page
        if user.password == password:
            session['logged_in'] = user.id
            flash('Welcome back, ' + user.first_name + '!')
            return redirect('/')
        # if password is incorrect, redirects to login page
        else:
            flash('Incorrect login. Please try again.')
            return redirect('/login')
    # if username is not in the database, redirects to the registration form
    else:
        flash('Username not found. Please register!')
        return redirect('/register')


@app.route('/logout')
def process_logout():
    """Processes user logout"""

    del session['logged_in']

    flash('See you next time!')
    return redirect('/')


@app.route('/register')
def register_form():
    """Redirects the user to the registration form"""

    return render_template('register_form.html')


@app.route('/process_registration', methods=['POST'])
def process_registration():
    """Processes user registration form"""

    username = request.form.get('username')
    user = User.query.filter_by(username=username).first()

    # if username does not already exist in the database,
    # gets all the user entered values from the registration form
    if not user:
        first_name = request.form.get('fname')
        last_name = request.form.get('lname')
        password = request.form.get('password')
        email = request.form.get('email')
        timestamp = datetime.now()

        # creates a new user instance
        new_user = User(username=username,
                        password=password,
                        confirmed_at=timestamp,
                        first_name=first_name,
                        last_name=last_name,
                        email=email)

        # adds the new user instance to the database and saves
        db.session.add(new_user)
        db.session.commit()

        # logs new user in
        session['logged_in'] = new_user.id

        flash("Account created. Hello, " + username + "!")
        return redirect('/')
    # if username exists, asks to pick new username and redirects to registration form
    else:
        flash('Username already exists!')
        return redirect('/register')


# Plant Routes *********************************


@app.route('/plant/<plant_id>')
def show_plant_details(plant_id):
    """Show individual plant's page"""

    plant = Plant.query.get(plant_id)

    return render_template('plant.html',
                           plant_id=plant.plant_id,
                           plant_name=plant.name,
                           plant_species=plant.species,
                           plant_img=plant.image,
                           water_icon=plant.get_water('icon'),
                           water=plant.get_water(),
                           sun_icon=plant.get_sun('icon'),
                           sun=plant.get_sun(),
                           humidity_icon=plant.get_humidity('icon'),
                           humidity=plant.get_humidity(),
                           temp_icon=plant.get_temp('icon'),
                           temp=plant.get_temp())


@app.route('/new_plant')
def add_new_plant():
    """Shows form for adding new plant"""

    WATER = Plant.WATER.keys()
    SUN = Plant.SUN.keys()
    HUMIDITY = Plant.HUMIDITY.keys()
    TEMP = Plant.TEMPERATURE.keys()

    return render_template('new_plant_form.html',
                           WATER=WATER,
                           SUN=SUN,
                           HUMIDITY=HUMIDITY,
                           TEMP=TEMP)


@app.route('/process_new_plant', methods=['POST'])
def process_new_plant():
    """Gets the user input from new plant form and adds to the database"""

    # if plant name not in the db, will create plant, else will not
    name = request.form.get('plant_name').title()
    if Plant.query.filter_by(name=name).all() == []:

        # gets all the user-entered data from the new plant form
        species = request.form.get('plant_species').title()
        image = request.form.get('plant_image')
        water = request.form.get('water')
        sun = request.form.get('sun')
        humidity = request.form.get('humidity')
        temp = request.form.get('temp')

        # creates new plant
        new_plant = Plant(name=name, species=species, image=image, water=water,
                          sun=sun, humidity=humidity, temperature=temp)

        # adds and saves new plant in the database
        db.session.add(new_plant)
        db.session.commit()

        flash(name + " has been added")
        return redirect('/plant/'+str(new_plant.plant_id))
    else:
        flash("Plant already exists", "warning")
        return redirect('/new_plant')


@app.route('/add_to_plant', methods=['POST'])
def add_missing_plant_info():
    """Fills out missing fields for plant."""

    # gets column being edited, new value, and plant being edited from ajax
    col_to_edit = request.form.get('columnToEdit')
    value = request.form.get('newValue')
    plant_id = int(request.form.get('plantId'))

    # gets plant being edited and updated the column value for that plant
    Plant.query.filter_by(plant_id=plant_id).update({col_to_edit: value})
    db.session.commit()

    # check to see if col to edit is a plant spec of sun, water, humidity, or temp
    spec = get_plant_specs(Plant.query.get(plant_id), col_to_edit)
    if spec:
        value = spec

    # sends back the the column and new value for html update
    edit = {'col': col_to_edit,
            'val': value}

    return jsonify(edit)


@app.route('/update_plant/<plant_id>', methods=['GET'])
def update_plant(plant_id):
    """Updates plant"""

    plant = Plant.query.get(plant_id)
    WATER = Plant.WATER.keys()
    SUN = Plant.SUN.keys()
    HUMIDITY = Plant.HUMIDITY.keys()
    TEMP = Plant.TEMPERATURE.keys()

    return render_template('update_plant.html',
                           plant_id=plant.plant_id,
                           plant_name=plant.name,
                           plant_species=plant.species,
                           plant_img=plant.image,
                           water=plant.get_water('summary'),
                           sun=plant.get_sun('summary'),
                           humidity=plant.get_humidity('summary'),
                           temp=plant.get_temp('summary'),
                           WATER=WATER,
                           SUN=SUN,
                           HUMIDITY=HUMIDITY,
                           TEMP=TEMP)


@app.route('/process_update_plant/<plant_id>', methods=['POST'])
def process_update_plant(plant_id):
    """Gets the user input from updating plant and updates the database"""
    plant = Plant.query.get(plant_id)

    # if plant name not in the db, will update plant, else will not
    name = request.form.get('plant_name').title().rstrip()
    if Plant.query.filter_by(name=name).all() == [] or Plant.query.filter_by(name=name).first() == plant:

        # gets all the user-entered data from the update plant form
        plant.name = request.form.get('plant_name')
        plant.species = request.form.get('plant_species').title()
        plant.image = request.form.get('plant_image')
        plant.water = request.form.get('water')
        plant.sun = request.form.get('sun')
        plant.humidity = request.form.get('humidity')
        plant.temperature = request.form.get('temp')

        # saves updated plant in the database
        db.session.commit()

        flash(name + " has been updated")
        return redirect('/plant/' + str(plant_id))
    # if user deletes plant name, will not submit
    elif name == '':
        flash("Plant name cannot be blank", "warning")
        return redirect('/update_plant/' + str(plant_id))
    # if user tries to update plant name to a name that already exists in db, will not submit
    else:
        flash("Plant name already exists", "warning")
        return redirect('/update_plant/' + str(plant_id))


@app.route('/delete_request', methods=['POST'])
def process_delete():
    """Deletes plant from the database"""

    plant_id = int(request.form.get('dataPlant'))
    print '*' * 100
    print plant_id
    plant = Plant.query.get(plant_id)
    print plant
    name = plant.name
    db.session.delete(plant)
    db.session.commit()

    flash(name + ' was deleted')
    return 'Deleted plant'


@app.route('/all_plants')
def show_all_plants_by_name():
    """Show all plants by name."""

    all_plants = Plant.query.all()

    return render_template("plants_by_name.html", plants=all_plants)

# **************************** HELPER FUNCTIONS *******************************


def get_all_users():
    return User.query.all()


def get_plant_specs(plant, spec, key='description'):
    """Returns a specific plant attribute for a specific plant"""

    if spec == 'water':
        return plant.get_water(key)
    elif spec == 'sun':
        return plant.get_sun(key)
    elif spec == 'humidity':
        return plant.get_humidity(key)
    elif spec == 'temp':
        return plant.get_temp(key)
    else:
        return None


if __name__ == "__main__":

    connect_to_db(app)
    app.debug = True

    app.run(host="0.0.0.0")
