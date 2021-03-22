from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Payments"),
			"icon": "fa fa-star",
			"items": [
				{
					"type": "doctype",
					"name": "PayPal Settings",
					"description": _("PayPal payment gateway settings"),
				},
				{
					"type": "doctype",
					"name": "Razorpay Settings",
					"description": _("Razorpay Payment gateway settings"),
				},
			]
		},
		{
			"label": _("Backup"),
			"items": [
				{
					"type": "doctype",
					"name": "Dropbox Settings",
					"description": _("Dropbox backup settings"),
				},
			]
		},
		{
			"label": _("Authentication"),
			"items": [
				{
					"type": "doctype",
					"name": "Social Login Keys",
					"description": _("Enter keys to enable login via Facebook, Google, GitHub."),
				},
				{
					"type": "doctype",
					"name": "LDAP Settings",
					"description": _("Ldap settings"),
				},
				{
					"type": "doctype",
					"name": "OAuth Client",
					"description": _("Register OAuth Client App"),
				},
				{
					"type": "doctype",
					"name": "OAuth Provider Settings",
					"description": _("Settings for OAuth Provider"),
				},
			]
		}
	]
