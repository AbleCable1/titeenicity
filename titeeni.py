from flask import Flask, render_template, request, url_for, redirect, jsonify
import uuid, datetime, time, requests, boto3, json, traceback
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute
from botocore.exceptions import ClientError

#Environment constants, redefine depending on the environment
BASE_URL = "http://localhost:5000/"
AWS_EMAIL_SENDER_ADDRESS = "TiteeniCity <noreply@titeeni.city>"
AWS_DYNAMODB_REGION = "eu-central-1"
CAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
CAPTCHA_PUBLIC_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
MAILGUN_API_KEY = ""


app = Flask(__name__, static_url_path='/static')


# General constants

RAW_F = ""
with open("qrcodes.json", "r", encoding="utf-8") as f:
    RAW_F = f.read()
QR_CODES = json.loads(RAW_F)
with open("items.json", "r", encoding="utf-8") as f:
    RAW_F = f.read()
ITEM_IMGURLS_AND_NAMES = json.loads(RAW_F)

FAILED_REGISTRATION_MSG = """
Ou nou, joko pelaajanimi tai sähköposti on jo rekisteröity järjestelmään, 
tai sitten unohdit täyttää CAPTCHA:n. Palaa edelliselle sivulle ja yritä uudelleen.
"""
INVALID_PLAYER_ID_ERROR_MSG = """
Ou nou, rekisteröityä pelaajaa annetuilla tiedoilla ei löytynyt. Palaa edelliselle sivulle ja yritä uudelleen.
"""

#Email sending:

CHARSET = "UTF-8"
SUBJECT_REGISTRATION_SUCCESS = "Olet rekisteröitynyt titeeni.cityyn"

BODY_TEXT_REGISTRATION_SUCCESS = """Hei <username>,
Olet onnistuneesti rekisteröitynyt titeeni.cityyn. 

Alla olevaa linkkiä seuraamalla pääset tarkastelemaan pelihahmoasi:

<linkki>

Onnea matkaan

Tämä viesti on lähetetty automaattisesti
"""   
            
BODY_HTML_REGISTRATION_SUCCESS = """<html>
<head></head>
<body>
  <b>Hei <username>,</b>
  <p>Olet onnistuneesti rekisteröitynyt titeeni.cityyn. 
  Alla olevaa linkkiä seuraamalla pääset tarkastelemaan pelihahmoasi:<br><br>
  <linkki><br><br>Onnea matkaan<br><br>Tämä viesti on lähetetty automaattisesti</p>
</body>
</html>
"""


def send_email(recipient, subject, body, body_html):
    try:
        payload = {'from': AWS_EMAIL_SENDER_ADDRESS, 'to': recipient, 'subject': subject, 'text': body, 'html': body_html}
        r = requests.post("https://api.mailgun.net/v3/titeeni.city/messages", data=payload, auth=('api', MAILGUN_API_KEY))

        if r.status_code < 300 and r.status_code >= 200:
            return True

        return False
    except Exception:
        traceback.print_exc()
        return False

def send_registration_email(email, link, username):
    send_email(email, SUBJECT_REGISTRATION_SUCCESS, 
        BODY_TEXT_REGISTRATION_SUCCESS.replace('<linkki>', link).replace('<username>', username), 
        BODY_HTML_REGISTRATION_SUCCESS.replace('<linkki>', link).replace('<username>', username))



#PynamoDB models
class PlayerModel(Model):
    class Meta:
        table_name = 'titeeni-player'
        region = AWS_DYNAMODB_REGION
    key = UnicodeAttribute(hash_key=True)
    username = UnicodeAttribute()
    email = UnicodeAttribute()
    guild = UnicodeAttribute()

    hat = UnicodeAttribute(null=True)
    clothing = UnicodeAttribute(null=True)
    item = UnicodeAttribute(null=True)
    drink = UnicodeAttribute(null=True)

    avail_hats = UnicodeAttribute(null=True) # A comma-separated list of hats
    avail_clothings = UnicodeAttribute(null=True) # A comma-separated list of ...
    avail_items = UnicodeAttribute(null=True) # ...
    avail_drinks = UnicodeAttribute(null=True) # ...

class UsedQrCodeModel(Model):
    class Meta:
        table_name = 'titeeni-usedqrcode'
        region = AWS_DYNAMODB_REGION
    qrcode_key = UnicodeAttribute(hash_key=True)

#Helper methods
def verify_captcha_response(captcha_response):
    try:
        payload = {'secret': CAPTCHA_SECRET_KEY, 'response': captcha_response}
        r = requests.post("https://www.google.com/recaptcha/api/siteverify", data=payload)

        if r.status_code < 300 and r.status_code >= 200:
            response = r.json()
            return response['success']

        return False
    except Exception:
        return False

def get_item_imgurl_and_name(item):
    return ITEM_IMGURLS_AND_NAMES[item]

def validate_uname_and_email(uname, em):
    players = list(PlayerModel.scan())
    for pl in players:
        if pl.username == uname or pl.email == em:
            return False
    return True

def get_player_by_username(uname):
    players = list(PlayerModel.scan())
    for pl in players:
        if pl.username == uname:
            return pl
    return None

def is_qrcode_valid_and_unused(qrcode_key):
    if qrcode_key not in QR_CODES:
        return False

    try:
        usedMod = UsedQrCodeModel.get(qrcode_key) #Raises exception if model does not exist
        return False
    except Exception:
        return True

def use_qrcode(player, qrcode_key):
    def get_list_attr(player, attr):
        content = getattr(player, attr)
        if not content:
            return []
        return content.split(',')

    if not is_qrcode_valid_and_unused(qrcode_key):
        return 
    qrcode_content = QR_CODES[qrcode_key]

    list_of_items = get_list_attr(player, qrcode_content['type'])
    list_of_items.append(qrcode_content['item'])
    setattr(player, qrcode_content['type'], ','.join(list_of_items))
    player.save()

    used_qrcode_model = UsedQrCodeModel(qrcode_key)
    used_qrcode_model.save()

def serialize_player(player):
    def serialize_list_attribute_contents(list_attribute_contents):
        if not list_attribute_contents:
            return []
        raw_list = list_attribute_contents.split(',')

        res = []
        for item in raw_list:
            res.append({'label': get_item_imgurl_and_name(item)['name'], 'value': item})

        return res

    def get_itemurl(item):
        if not item:
            return ""
        return get_item_imgurl_and_name(item)['url']

    return {
        'username': player.username,
        'email': player.email,
        'guild': player.guild,
        
        'hat': player.hat,
        'clothing': player.clothing,
        'item': player.item,
        'drink': player.drink,

        'hat_url': get_itemurl(player.hat),
        'clothing_url': get_itemurl(player.clothing),
        'item_url': get_itemurl(player.item),
        'drink_url': get_itemurl(player.drink),
        
        'avail_hats': serialize_list_attribute_contents(player.avail_hats),
        'avail_clothings': serialize_list_attribute_contents(player.avail_clothings),
        'avail_items': serialize_list_attribute_contents(player.avail_items),
        'avail_drinks': serialize_list_attribute_contents(player.avail_drinks)
    }

def deserialize_and_save_player(player, data):
    def item_in_list(item_name, comma_separated_list):
        if not comma_separated_list:
            return False
        return item_name in comma_separated_list.split(',')

    if data['hat'] and item_in_list(data['hat'], player.avail_hats):
        player.hat = data['hat']
    else:
        player.hat = None

    if data['clothing'] and item_in_list(data['clothing'], player.avail_clothings):
        player.clothing = data['clothing']
    else:
        player.clothing = None

    if data['item'] and item_in_list(data['item'], player.avail_items):
        player.item = data['item']
    else:
        player.item = None

    if data['drink'] and item_in_list(data['drink'], player.avail_drinks):
        player.drink = data['drink']
    else:
        player.drink = None

    player.save()

#Views

@app.route('/', methods=['GET', 'POST'])
def index_view():
    try:
        if request.method == 'POST':
            if verify_captcha_response(request.form['g-recaptcha-response']):

                key = str(uuid.uuid4())
                username = request.form['username']
                email = request.form['email']
                guild = request.form['guild']
                if not validate_uname_and_email(username, email):
                    raise Exception("")

                player = PlayerModel(key, username=username, email=email, guild=guild)
                player.save()

                link = BASE_URL + "player/" + key

                send_registration_email(email, link, username)
                
                return redirect(link, code=302)
            else:
                return FAILED_REGISTRATION_MSG, 400
    except Exception:
        traceback.print_exc()
        return FAILED_REGISTRATION_MSG, 400

    return render_template('index.html', captchakey=CAPTCHA_PUBLIC_KEY)

@app.route('/qrcode/<qrcodekey>', methods=['GET', 'POST'])
def qrcode_view(qrcodekey):
    try:
        if request.method == 'POST':
            if verify_captcha_response(request.form['g-recaptcha-response']):

                username = request.form['username']
                player = get_player_by_username(username)

                if player is None:
                    return INVALID_PLAYER_ID_ERROR_MSG, 400

                playerlink = BASE_URL + "player/" + player.key

                if is_qrcode_valid_and_unused(qrcodekey):

                    use_qrcode(player, qrcodekey)

                    imgurl_and_name = get_item_imgurl_and_name(QR_CODES[qrcodekey]['item'])
                   
                    return render_template('qrcodeview.html', opened=True, empty=False, playerlink=playerlink, 
                        itemname=imgurl_and_name['name'], itemimgurl=imgurl_and_name['url'], 
                        captchakey=CAPTCHA_PUBLIC_KEY)

                else:
                    return render_template('qrcodeview.html', opened=True, empty=True, 
                        playerlink=playerlink, itemname='', itemimgurl='', captchakey=CAPTCHA_PUBLIC_KEY)
    except Exception:
        traceback.print_exc()

    return render_template('qrcodeview.html', opened=False, empty=True, playerlink='', itemname='', 
        itemimgurl='', captchakey=CAPTCHA_PUBLIC_KEY)

@app.route('/player/<key>', methods=['GET', 'POST'])
def player_view(key):
    def nullstring_handler(input):
        if input == 'null':
            return None
        return input
    try:
        player = PlayerModel.get(key)
        if request.method == 'POST':
            if verify_captcha_response(request.form['g-recaptcha-response']):
                data = {
                    'hat': nullstring_handler(request.form['hat']),
                    'clothing': nullstring_handler(request.form['clothing']),
                    'item': nullstring_handler(request.form['item']),
                    'drink': nullstring_handler(request.form['drink']),
                }
                deserialize_and_save_player(player, data)

        return render_template('playerview.html', player=serialize_player(player), captchakey=CAPTCHA_PUBLIC_KEY)

    except Exception:
        traceback.print_exc()
        return INVALID_PLAYER_ID_ERROR_MSG, 400


if __name__ == '__main__':
    app.run()