import frappe
from employee_self_service.mobile.v2.modules import log
from employee_self_service.mobile.v2.models import LoginModel
from pydantic import ValidationError
from bs4 import BeautifulSoup



endpoints = {
    "login": {"methods": {"POST"}, "function": Auth().login,"model":LoginModel, "allow_guest": True},
    "get_access_token": {
        "methods": {"GET"},
        "function": Auth().get_access_token_from_refresh_token,
        "model":RefreshTokenModel,
        "allow_guest": True,
    },
    "revoke_access_token": {
        "methods": {"POST"},
        "function": Auth().revoke_access_token,
        "model":RevokeTokenModel,
        "allow_guest": False,
    },
}

def get_allow_guest(type: str):
    endpoint = endpoints.get(type)
    return endpoint.get("allow_guest", False) if endpoint else False

@frappe.whitelist(methods=["POST", "GET", "PUT", "DELETE"], allow_guest=True)
@log()
def v1(type: str, data: dict | None = None, **kwargs):
    """
    Handle API requests with different HTTP methods.
    The data param (for POST) is converted to a Pydantic model for validation.
    """
    endpoint = endpoints.get(type)

    if not endpoint:
        return gen_response(404, "Endpoint not found.")

    if frappe.request.method not in endpoint["methods"]:
        return gen_response(405, "Method not allowed.")

    if not _has_permission(type):
        return gen_response(403, "Guest access not allowed for this endpoint.")

    data = data or {}

    model = endpoint.get("model")
    if model:
        data, error = _validate_data(model, data)
        if error:
            return gen_response(400, error)

    try:
        if frappe.request.method == "POST":
            frappe.db.begin()
        if not model:
            result = endpoint["function"](**data)
        else:
            result = endpoint["function"](data)

        if frappe.request.method == "POST":
            frappe.db.commit()
    except frappe.AuthenticationError:
        return gen_response(500, frappe.response["message"])
    except Exception as e:
        frappe.log_error(title="POS Error", message=frappe.get_traceback())
        return gen_response(500, str(e))

    return gen_response(200, frappe.response.get("message"), result)


def _has_permission(type: str) -> bool:
    """Check if guest access is allowed."""
    return get_allow_guest(type) or frappe.session.user != "Guest"


def _validate_data(model, data: dict):
    """Validate data with Pydantic model and return formatted error if any."""
    try:
        return model(**data), None
    except ValidationError as ve:
        error_details = [f"{error['loc'][0]}: {error['msg']}" for error in ve.errors()]
        return None, "Validation error: " + ", ".join(error_details)


def gen_response(status, message, data=None):
    frappe.response["http_status_code"] = status
    # Determine success or failure based on status code
    if 400 <= status < 600:
        frappe.response["status"] = "fail"
        frappe.response["message"] = BeautifulSoup(str(message)).get_text()  # Clean message for failure cases
    else:
        frappe.response["status"] = "success"
        frappe.response["message"] = message

    # Include data if provided
    if data is not None:
        frappe.response["data"] = data