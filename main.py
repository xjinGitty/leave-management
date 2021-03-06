from flask import Flask, render_template, request, g, session, flash, \
     redirect, url_for, abort
from flask.ext.openid import OpenID
from openid.extensions import pape
from flask_bootstrap import Bootstrap

from datetime import datetime

import redis

r = redis.StrictRedis(host='147.2.212.204', port=6379, db=0,
                      decode_responses=True)

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY = 'developmentzxddddd', DEBUG=True)
    oid = OpenID(app, safe_roots=[], extension_responses=[pape.Response])

    
    @app.before_request
    def before_request():
        g.user = None
        if 'openid' in session:
            g.user = r.hgetall(session['openid'])
    
    @app.route('/')
    def index():
        if g.user is None or 'openid' not in session:
            return redirect(url_for('login'))
        return render_template('index.html')
    
    
    @app.route('/login', methods=['GET', 'POST'])
    @oid.loginhandler
    def login():
        """Does the login via OpenID.  Has to call into `oid.try_login`
        to start the OpenID machinery.
        """
        # if we are already logged in, go back to were we came from
        if g.user is not None:
            print(oid.get_next_url())
            #return redirect(oid.get_next_url())
            return redirect(url_for('user_info'))
        if request.method == 'POST':
            openid = request.form.get('openid')
            if openid:
                pape_req = pape.Request([])
                return oid.try_login(openid, ask_for=['email', 'nickname'],
                                             ask_for_optional=['fullname'],
                                             extensions=[pape_req])
        return render_template('login.html', next='/user',
                               error=oid.fetch_error())
    
    
    @oid.after_login
    def create_or_login(resp):
        """This is called when login with OpenID succeeded and it's not
        necessary to figure out if this is the users's first login or not.
        This function has to redirect otherwise the user will be presented
        with a terrible URL which we certainly don't want.
        """
        session['openid'] = resp.identity_url
        if 'pape' in resp.extensions:
            pape_resp = resp.extensions['pape']
            session['auth_time'] = pape_resp.auth_time
        #user = User.query.filter_by(openid=resp.identity_url).first()
        user = r.hget(session['openid'], 'name')
        if user is not None:
            flash(u'Successfully signed in')
            g.user = user
            return redirect(oid.get_next_url())
        return redirect(url_for('create_profile', next=oid.get_next_url(),
                                name=resp.fullname or resp.nickname,
                                email=resp.email))
    
    
    @app.route('/create-profile', methods=['GET', 'POST'])
    def create_profile():
        """If this is the user's first login, the create_or_login function
        will redirect here so that the user can set up his profile.
        """
        if g.user is not None or 'openid' not in session:
            return redirect(url_for('index'))
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            if not name:
                flash(u'Error: you have to provide a name')
            elif '@' not in email:
                flash(u'Error: you have to enter a valid email address')
            else:
                flash(u'Profile successfully created')
                r.hmset(session['openid'], {'name':name, 'email':email})
                return redirect(oid.get_next_url())
        return render_template('create_profile.html', next_url=oid.get_next_url())
    
    
    @app.route('/profile', methods=['GET', 'POST'])
    def edit_profile():
        """Updates a profile"""
        if g.user is None:
            abort(401)
        form = g.user
        if request.method == 'POST':
            if 'delete' in request.form:
                r.delete(session['openid'])
                session['openid'] = None
                flash(u'Profile deleted')
                return redirect(url_for('index'))
            form['name'] = request.form['name']
            form['email'] = request.form['email']
            form['employtime'] = request.form['employtime']
            try:
                employtime = datetime.strptime(form['employtime'], '%Y%m')
            except ValueError:
                employtime = None
            if not form['name']:
                flash(u'Error: you have to provide a name')
            elif '@' not in form['email']:
                flash(u'Error: you have to enter a valid email address')
            elif not employtime:
                flash(u'Error: you have to give a correct date')
            else:
                flash(u'Profile successfully created')
                for item in ['name', 'email', 'employtime']:
                    g.user[item] = form[item]
                    r.hset(session['openid'], item, form[item])
                return redirect(url_for('edit_profile'))
        return render_template('edit_profile.html', form=form)
    
    @app.route('/user')
    def user_info():
        if g.user is None:
            abort(401)
        days = 15
        return render_template('user_info.html', days=days)

    @app.route('/logout')
    def logout():
        session.pop('openid', None)
        flash(u'You have been signed out')
        return redirect(oid.get_next_url())
    
    Bootstrap(app)
    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0')
