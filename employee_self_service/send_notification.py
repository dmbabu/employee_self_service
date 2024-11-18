import frappe
import requests
import json
from frappe import enqueue
import google.auth.transport.requests
from google.oauth2 import service_account
import os   
from frappe.utils import parse_val

event_mapping = {
    "before_save": "New",
    "after_save": "Save",
    "on_submit": "Submit",
    "before_cancel": "Cancel",
    "after_cancel": "Cancel",
    "days_after": "Days After",
    "days_before": "Days Before",
}


@frappe.whitelist()
def notification(doc, event):
    try:
        if frappe.db.exists("DocType","ESS Notification"):
            notification_processing(doc, event)
    except Exception as e:
        frappe.log_error(title="ESS Notification Trigger Error",message=frappe.get_traceback())


def get_user_tokens(notification_id, doc):
    to_users_data = []
    recipients = frappe.get_all(
        "ESS Notification Recipient",
        filters={"parent": notification_id},
        fields=["receiver_by_document_field", "receiver_by_role"],
    )

    for recipient in recipients:
        role_name = recipient["receiver_by_role"]
        user_field = doc.get(recipient["receiver_by_document_field"])
        get_users_data = frappe.db.sql(
            """
            SELECT u.email
            FROM `tabUser` u
            JOIN `tabHas Role` hr ON u.name = hr.parent
            WHERE hr.role = %s
        """,
            role_name,
            as_dict=True,
        )
        user_emails = [user["email"] for user in get_users_data]
        if user_field:
            user_emails.append(user_field)
        filters = [
            ["name","in",user_emails]
        ]
        to_users_data = frappe.get_all(
            "Employee Device Info",
            filters=filters,
            fields=["name","token"],
        )
    return to_users_data


def notification_processing(doc, event):
    if not doc.flags.in_insert:
        # value change is not applicable in insert
        event_mapping['on_change'] = 'Value Change'
    event_type = event_mapping.get(event)
    if not event_type:
        return
    notifications = frappe.get_all(
        "ESS Notification",
        filters={
            "enabled": 1,
            "event":event_type,
            "document_type": doc.doctype,
        },
        fields=["name", "subject", "message", "condition", "document_type","value_changed"],
    )
    if not notifications:
        return

    setting = frappe.get_doc("Employee Self Service Settings","Employee Self Service Settings")
    if not setting.get("enable_ess_notification"):
        return

    recipients = []
    for notification in notifications:
        if notification["condition"]:
            condition_result = frappe.safe_eval(
            notification["condition"], None, {"doc": doc})
            if not condition_result:
                continue
        if event_type == "Value Change" and not doc.is_new():
                if not frappe.db.has_column(doc.doctype, notification.value_changed):
                    continue
                else:
                    doc_before_save = doc.get_doc_before_save()
                    field_value_before_save = doc_before_save.get(
                        notification.value_changed) if doc_before_save else None
                    field_value_before_save = parse_val(field_value_before_save)
                    if (doc.get(notification.value_changed) == field_value_before_save):
                        # value not changed
                        continue
                    else:
                        recipients = get_user_tokens(notification["name"], doc)
                        send_notification(doc, notification, recipients)
        else:
            recipients = get_user_tokens(notification["name"], doc)
            send_notification(doc, notification, recipients)

def send_notification(doc, notification, recipients):
    subject = frappe.render_template(notification["subject"], {"doc": doc})
    message = frappe.render_template(notification["message"], {"doc": doc})
    for user in recipients:
        notification_log(
            notification["name"],
            doc.doctype,
            subject,
            message,
            user.get("name"),
            user.get("token")
        )

def notification_log(notification_name, doctype, subject, message, recipient,token):
    notification_log = frappe.new_doc("ESS Notification Log")
    notification_log.notification_name = notification_name
    notification_log.document_type = doctype
    notification_log.subject = subject
    notification_log.message = message
    notification_log.recipient = recipient
    notification_log.token = token
    notification_log.insert(ignore_permissions=True)
