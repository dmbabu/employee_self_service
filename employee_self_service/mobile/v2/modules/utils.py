import frappe
from bs4 import BeautifulSoup
from frappe.utils import cstr
import wrapt

class ESSAPI:
    def get_employee_by_user(self, user, fields=["name"]):
        if isinstance(fields, str):
            fields = [fields]
        emp_data = frappe.get_cached_value(
            "Employee",
            {"user_id": user},
            fields,
            as_dict=1,
        )
        return emp_data

    def validate_employee_data(self, employee_data):
        if not employee_data.get("company"):
            return self.gen_response(
                500,
                "Company not set in employee doctype. Contact HR manager to set the company.",
            )

    def get_ess_settings(self):
        return frappe.get_doc("Employee Self Service Settings", "Employee Self Service Settings")

    def get_global_defaults(self):
        return frappe.get_doc("Global Defaults", "Global Defaults")

    def remove_default_fields(self, data):
        for row in ["owner", "creation", "modified", "modified_by", "docstatus", "idx", "doctype", "links"]:
            if data.get(row):
                del data[row]
        return data

    def prepare_json_data(self, key_list, data):
        return_data = {}
        for key in data:
            if key in key_list:
                return_data[key] = data.get(key)
        return return_data

    def get_actions(self, doc, doc_data=None):
        from frappe.model.workflow import get_transitions

        if not frappe.db.exists("Workflow", dict(document_type=doc.get("doctype"), is_active=1)):
            doc_data["workflow_state"] = doc.get("status")
            return []
        transitions = get_transitions(doc)
        actions = [row.get("action") for row in transitions]
        return actions

    def check_workflow_exists(self, doctype):
        doc_workflow = frappe.get_all(
            "Workflow",
            filters={"document_type": doctype, "is_active": 1},
            fields=["workflow_state_field"],
        )
        return doc_workflow[0].workflow_state_field if doc_workflow else False

    def update_workflow_state(self, reference_doctype, reference_name, action):
        try:
            from frappe.model.workflow import apply_workflow
            doc = frappe.get_doc(reference_doctype, reference_name)
            apply_workflow(doc, action)
            return self.gen_response(200, "Workflow State Updated Successfully")
        except frappe.PermissionError:
            return self.gen_response(500, f"Not permitted for update {reference_doctype}")
        except Exception as e:
            frappe.db.rollback()
            return self.exception_handler(e)

    def convert_timezone(self, timestamp, from_timestamp, time_zone):
        from pytz import UnknownTimeZoneError, timezone
        fromtimezone = timezone(from_timestamp).localize(timestamp)
        try:
            return fromtimezone.astimezone(timezone(time_zone))
        except UnknownTimeZoneError:
            return fromtimezone

    def get_system_timezone(self) -> str:
        """Return the system timezone."""
        return frappe.get_system_settings("time_zone") or "Asia/Kolkata"