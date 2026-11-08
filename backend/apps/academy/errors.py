from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = 409
    default_detail = "This conflicts with the current state."


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "This is not available right now."


class BadGateway(APIException):
    status_code = 502
    default_detail = "The payment provider could not be reached."