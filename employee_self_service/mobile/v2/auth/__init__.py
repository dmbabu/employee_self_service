import frappe
from frappe import _
from employee_self_service.mobile.v2.models import LoginModel

class Auth:
    def __init__(self) -> None:
        self.user = frappe.session.user

    def login(self, data:LoginModel):
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(data.usr,data.pwd)
        login_manager.post_login()
        self.user = frappe.session.user
        self.validate_employee()
        if frappe.response["message"] == "Logged In":
            frappe.response["user"] = self.user
            frappe.response["key_details"] = self.generate_key(login_manager.user)
            frappe.response["pin"] = self.user_pin
            frappe.response["user_type"] = self.user_type

    def generate_key(self, user):
        user_details = frappe.get_doc("User", user)
        api_secret = api_key = ""
        if not user_details.api_key and not user_details.api_secret:
            api_secret = frappe.generate_hash(length=15)
            api_key = frappe.generate_hash(length=15)
            user_details.api_key = api_key
            user_details.api_secret = api_secret
            user_details.save(ignore_permissions=True)
        else:
            api_secret = user_details.get_password("api_secret")
            api_key = user_details.get("api_key")
        return {"api_secret": api_secret, "api_key": api_key}

    def validate_employee(self):
        if not frappe.db.exists("Employee", dict(user_id=self.user)):
            frappe.response["message"] = "Please link Employee with this user"
            raise frappe.AuthenticationError(frappe.response["message"])