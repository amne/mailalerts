import imaplib
import email
import json
import oauth2
import sys
import re
from pushover import Client
from twilio.rest import TwilioRestClient

config = json.loads(open('config.json').read())
pushover_api_key = config.get('pushover_api_key', False)
twilio = False
if config.get('twilio_account_sid', False):
    twilio = TwilioRestClient(account=config.get('twilio_account_sid'), token=config.get('twilio_account_token', False))

def getMail(n, gmail_conn):
    mailstuff = False
    (code,  mail) = gmail_conn.fetch(n, '(RFC822)')
    if 'OK' != code:
	return False
    for part in mail:
	if isinstance(part, tuple):
	    mailstuff = email.message_from_string(part[1])
	    break
    # gmail_conn.store(n, '+FLAGS', '\\Seen')
    return mailstuff

def connectGmail(usermail):
    tokens = json.loads(open(config.get('gmail_token_file')).read())
    refresh_token = tokens.get('refresh')
    access_token = tokens.get('token')
    oauth_token_string = oauth2.GenerateOAuth2String(usermail, access_token, False)
    try:
	gmail_conn = imaplib.IMAP4_SSL(config.get('gmail_imap','imap.gmail.com'));
	gmail_conn.authenticate('XOAUTH2', lambda p: oauth_token_string)
    except imaplib.IMAP4.error as gmail_error:
	print gmail_error
	if re.search('Invalid credentials', str(gmail_error)):
	    print "getting new gmail token"
	    refresh_token_response = oauth2.RefreshToken(config.get('gmail_client_id'), config.get('gmail_client_secret'), refresh_token)
	    token_data = json.dumps({ 'refresh' : refresh_token, 'token' : refresh_token_response['access_token'] })
	    f = open(config.get('gmail_token_file'), 'w')
	    f.write(token_data)
	    f.close()
	return False
    return gmail_conn



gmail_conn = False
try_count = 3
k = 0
# fetch unread messages with X0DCRITICAL in subject
while not gmail_conn:
    gmail_conn = connectGmail(config.get('gmail_user'))
    k = k + 1
    if k > try_count:
	print 'Giving up on gmail'
	exit()
gmail_conn.select('INBOX', readonly=1)
(code, mails) = gmail_conn.search(None, '(UNSEEN SUBJECT "%s")' % 'X0DCRITICAL')
print "gmail returned code %s \n" % code

k=0
max_batch=3

if code == 'OK':
    msgs = mails[0].split()
    print "processing %s messages" % len(msgs)
    for n in msgs:
	k=k+1
	if k > max_batch:
	    break
	mail = getMail(n, gmail_conn)
	if False != mail:
	    print "Processing message \"%s\" from %s" % (mail.get('Subject'), mail.get('From'))
	    if False != pushover_api_key:
		print "- Sending pushover notifications"
		for user in config.get('alerts_pushover', []):
		    
		    Client(user, api_token=pushover_api_key).send_message("Topic: %s \n From: %s" % (mail.get('Subject'), mail.get('From')))
	    if twilio:
		print "- Sending calls"
		for user in config.get('alerts_sms', []):
		    res = twilio.messages.create(
		     body="%s from %s" % (mail.get('Subject'), mail.get('From')),
		     to=user,
		     from_=config.get('twilio_phone_no')
		    )

