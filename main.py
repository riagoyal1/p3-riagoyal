import urllib.request, urllib.error, urllib.parse, json
from flask import Flask, render_template, request, session, redirect, url_for
import ssl

# ctx = ssl.create_default_context()
# ctx.check_hostname = False
# ctx.verify_mode = ssl.CERT_NONE

app = Flask(__name__)

from secretcode import CLIENT_ID, CLIENT_SECRET

GRANT_TYPE = 'authorization_code'

def pretty(obj):
    return json.dumps(obj, sort_keys=True, indent=2)

# This is a code we'll use to crypotgraphically secure our sessions
# I set it to CLIENT_SECRET for simplicity here.
app.secret_key = CLIENT_SECRET


### Helper functions ####

### This adds a header with the user's access_token to Spotify requests
def spotifyurlfetch(url, access_token, params=None):
    headers = {'Authorization': 'Bearer ' + access_token}
    req = urllib.request.Request(
        url=url,
        data=params,
        headers=headers
    )
    response = urllib.request.urlopen(req)
    return response.read()


### Handlers ###

### this will handle our home page
@app.route("/")  # get method
def index():
    time_period = request.args.get("time_period", "medium_term")
    app.logger.info(time_period)
    if 'user_id' in session:
        # if logged in, get their top tracks
        url = "https://api.spotify.com/v1/me/top/tracks?time_range=%s" % time_period
        # url = "https://api.spotify.com/v1/users/%s/playlists" % session['user_id']
        # in the future, should make this more robust so it checks
        # if the access_token is still valid and retrieves a new one
        # using refresh_token if not
        try:
            response = json.loads(spotifyurlfetch(url, session['access_token']))
        except:
            return logout_handler()
        tracks = response["items"]
    else:
        tracks = None

    return render_template('oauth.html', user=session, tracks=tracks, time_period=time_period)


### this handler will handle our authorization requests
@app.route("/auth/login")
def login_handler():
    # after  login; redirected here
    # did we get a successful login back?
    args = {}
    args['client_id'] = CLIENT_ID
    app.logger.info(CLIENT_ID)

    verification_code = request.args.get("code")
    if verification_code:
        # if so, we will use code to get the access_token from Spotify
        # This corresponds to STEP 4 in https://developer.spotify.com/web-api/authorization-guide/

        args["client_secret"] = CLIENT_SECRET
        args["grant_type"] = GRANT_TYPE
        # store the code we got back from Spotify
        args["code"] = verification_code
        # the current page
        args['redirect_uri'] = request.base_url
        data = urllib.parse.urlencode(args).encode("utf-8")
        app.logger.info(data)

        # We need to make a POST request, according to the documentation
        # headers = {'content-type': 'application/x-www-form-urlencoded'}
        url = "https://accounts.spotify.com/api/token"
        req = urllib.request.Request(url)
        app.logger.info(data)
        response = urllib.request.urlopen(req, data=data)
        response_dict = json.loads(response.read())
        access_token = response_dict["access_token"]
        refresh_token = response_dict["refresh_token"]

        # Download the user profile. Save profile and access_token
        # in Datastore; we'll need the access_token later

        ## the user profile is at https://api.spotify.com/v1/me
        profile = json.loads(spotifyurlfetch('https://api.spotify.com/v1/me',
                                             access_token))

        ## Put user info in session
        ## it is not generally a good idea to put all of this in
        ## session, because there is a risk of sensitive info
        ## (like access token) being exposed.
        session['user_id'] = profile["id"]
        session['displayname'] = profile["display_name"]
        session['access_token'] = access_token
        session['profile_url'] = profile["external_urls"]["spotify"]
        session['api_url'] = profile["href"]
        session['refresh_token'] = refresh_token
        if profile.get('images') is not None:
            session['img'] = profile["images"][0]["url"]

        ## okay, all done, send them back to the App's home page
        app.logger.info("Print url: " + str(url_for('index')))
        return redirect(url_for('index'))
    else:
        # not logged in yet-- send the user to Spotify to do that
        # This corresponds to STEP 1 in https://developer.spotify.com/web-api/authorization-guide/

        args['redirect_uri'] = request.base_url
        args['response_type'] = "code"
        # ask for the necessary permissions -
        # see details at https://developer.spotify.com/web-api/using-scopes/
        args['scope'] = "user-top-read"

        url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(args)
        app.logger.info("Print url: " + str(url))
        return redirect(url)


## this handler logs the user out by making the cookie expire
@app.route("/auth/logout")
def logout_handler():
    ## remove each key from the session!
    for key in list(session.keys()):
        session.pop(key)
    return redirect(url_for('index'))


if __name__ == "__main__":
    # Used when running locally only.
    # When deploying to Google AppEngine, a webserver process
    # will serve your app.
    app.run(host="localhost", port=8090, debug=True)
