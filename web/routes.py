"""Páginas existentes del equipo, servidas por la misma aplicación Flask."""

from flask import Blueprint, redirect, render_template

web = Blueprint("web", __name__)


@web.get('/time-machine')
@web.get('/time-machine.html')
@web.get('/time_machine')
@web.get('/time_machine.html')
def time_machine():
    return render_template('pages/workspace.html')


@web.get('/time-machine/legacy')
def time_machine_legacy():
    return render_template('pages/time_machine.html')


@web.get('/cities')
@web.get('/cities/<city_id>')
def city_profiles(city_id=None):
    if city_id:
        from flask import current_app
        current_app.extensions['earthlens_service'].get_city(city_id)
    return render_template('pages/workspace.html',workspace_panel='profile',workspace_city=city_id)


@web.get('/my-space')
def my_space():
    return render_template('pages/workspace.html',workspace_panel='events')


@web.get('/laboratory')
def laboratory():
    return render_template('pages/laboratory.html')


@web.get('/sources')
def scientific_sources():
    return render_template('pages/scientific.html',science_open=True)


@web.get("/")
@web.get("/index.html")
def index():
    return render_template('pages/workspace.html')


@web.get("/explorer")
@web.get("/explorer.html")
def explorer():
    return redirect("/")


@web.get("/results")
@web.get("/results.html")
def results():
    return render_template("pages/results.html")


@web.get("/compare")
@web.get("/compare.html")
def compare():
    return render_template("pages/compare.html")


@web.get("/missions")
def missions():
    return render_template("pages/missions.html")


@web.get("/about")
def about():
    return render_template("pages/about.html")


@web.get("/radar")
def radar():
    return render_template("pages/radar.html")


@web.get("/fingerprint")
def fingerprint():
    return render_template("pages/fingerprint.html")
