from flask import abort, request
from functools import wraps
from twilio.request_validator import RequestValidator
import os
import logging

# forked from https://www.twilio.com/docs/usage/tutorials/how-to-secure-your-flask-app-by-validating-incoming-twilio-requests
def twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Create an instance of the RequestValidator class
        token = os.environ.get('TWILIO_AUTH_TOKEN')
        validator = RequestValidator(token)

        # Validate the request using its URL, GET data,
        # and X-TWILIO-SIGNATURE header
        signature = request.headers.get('X-TWILIO-SIGNATURE')
        body = request.form
        if signature == None or body == None:
            return abort(400)

        logging.info('SMS: Validating Twilio Request %s %s', body.get('From'), signature)
        request_valid = validator.validate(request.url, body, signature)
        logging.info('SMS: Twilio request validity: %s', request_valid)

        if request_valid:
            return f(*args, **kwargs)
        else:
            return abort(403)
    return decorated_function
