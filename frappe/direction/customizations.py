# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import MySQLdb
import frappe, json
from frappe.utils import add_days, cint, flt, nowdate, getdate, get_site_path, get_files_path, comma_and, today, cstr, nowtime, now_datetime, get_last_day
from frappe.model.db_query import DatabaseQuery
from frappe.desk.reportview import get_match_cond
from frappe.model.mapper import get_mapped_doc

from frappe.model.document import Document
from frappe import _, msgprint, throw

@frappe.whitelist()
def sn_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select name from `tabSerial No`
					where item_code=%(item_code)s and not name in (select serial_no from `tabAsset` where not isnull(serial_no)
					and (status='Submitted' or status='Partially Depreciated'))
					and ({key} like %(txt)s)
					{mcond}
					order by
						if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
						name
					limit %(start)s, %(page_len)s""".format(**{
						'key': searchfield,
						'mcond':get_match_cond(doctype)
					}), {
						'txt': "%%%s%%" % txt,
						'_txt': txt.replace("%", ""),
						'start': start,
						'page_len': page_len,
						'item_code': filters.get('item_code')
					})

@frappe.whitelist()
def serial_n_query(doctype, txt, searchfield, start, page_len, filters):
	cond = ''
	if filters.get('item_code'):
		cond += 'and sn.item_code = "' + filters['item_code'] + '" '
	if filters.get('item_category'):
		cond += 'and i.item_category = "' + filters['item_category'] + '" '
	if filters.get('customer'):
		cond += 'and sn.customer = "' + filters['customer'] + '" '
	return frappe.db.sql("""select sn.name from `tabSerial No` sn left join `tabItem` i on sn.item_code=i.name
					where 1=1 {cond}
					and ({key} like %(txt)s)
					{mcond}
					order by
						if(locate(%(_txt)s, sn.name), locate(%(_txt)s, sn.name), 99999),
						sn.name
					limit %(start)s, %(page_len)s""".format(**{
						'key': 'sn.name',
						'mcond':get_match_cond(doctype),
						'cond': cond
					}), {
						'txt': "%%%s%%" % txt,
						'_txt': txt.replace("%", ""),
						'start': start,
						'page_len': page_len
					})

@frappe.whitelist()
def get_category_details(asset_category):
	ret = frappe.db.get_value("Asset Category", asset_category,
		["depreciation_method", "total_number_of_depreciations", "frequency_of_depreciation"], as_dict=1)

	return ret

@frappe.whitelist()
def set_current_counters(current_date, a4_bw=None, a3_bw=None, a4_color=None, a3_color=None, serial_no=None):
	if not a4_bw:
		a4_bw = 0
	if not a3_bw:
		a3_bw = 0
	if not a4_color:
		a4_color = 0
	if not a3_color:
		a3_color = 0
	cur_date = frappe.db.get_value("Serial No", serial_no, "counter_updated_in", as_dict=1)

	frappe.db.sql("""update `tabSerial No` sn set current_bw_a4=%(a4_bw)s, current_bw_a3=%(a3_bw)s, current_color_a4=%(a4_color)s,
					current_color_a3=%(a3_color)s , counter_updated_in=%(current_date)s
					where name=%(serial_no)s and ifnull(counter_updated_in, '1900-01-01')<=%(current_date)s""",
					{"a4_bw": a4_bw, "a3_bw": a3_bw, "a4_color": a4_color, "a3_color": a3_color, "serial_no": serial_no, "current_date": current_date})

	if not cur_date.counter_updated_in or getdate(cur_date.counter_updated_in) <= getdate(current_date):
		frappe.msgprint(_("Counters Updated Successfuly !"))

	return

@frappe.whitelist()
def set_Maint_type(maintenance_contract_type=None, sales_order=None):
	frappe.db.sql("""update `tabSerial No` sn
					right join `tabSales Order Item` soi on soi.serial_n=sn.name and soi.parent=%(sales_order)s
					set sn.maintenance_contract_type=%(maintenance_contract_type)s
					where soi.parent=%(sales_order)s""",
					{"sales_order": sales_order, "maintenance_contract_type": maintenance_contract_type})

	# frappe.msgprint(_("Maintenance Type Updated Successfuly for Serial Numbers enclosed!"))

	return

@frappe.whitelist()
def set_dep_address(installation_note=None, address=None):
	frappe.db.sql("""update `tabSerial No` sn
					right join `tabInstallation Note Item` ini on ini.serial_n=sn.name and ini.parent=%(installation_note)s
					set sn.department=ini.department, sn.address=%(address)s
					where ini.parent=%(installation_note)s""",
					{"installation_note": installation_note, "address": address})

	frappe.msgprint(_("Address and Department Updated Successfuly for Serial Numbers enclosed!"))

	return

@frappe.whitelist()
def get_dn(delivery_note):
	source_dn = frappe.db.sql("""select * from `tabDelivery Note`
						where docstatus=1 and name=%s""", (delivery_note), as_dict=1)
	source_items = frappe.db.sql("""select dni.item_code, dni.item_name, dni.description, dni.qty, dni.serial_no, dni.against_sales_order, dni.related_maintenance_visit,
						dni.stock_uom, dni.parent as dn, dni.name, dni.machine_serial_no, i.installation_time from `tabDelivery Note Item` dni
						left join `tabItem` i on i.name=dni.item_code
						where dni.docstatus=1 and dni.parent=%s""", (delivery_note), as_dict=1)
	so_items = []
	for items in source_items:
		serial_nos = get_serial_nos(items.serial_no)
		for serial_no in serial_nos:
			if frappe.db.exists("Serial No", serial_no):
				so_x = {"item_code":items.item_code, "item_name":items.item_name, "machine_serial_no":items.machine_serial_no, "qty":1,
						"serial_no":items.serial_no, "serial_n":items.serial_no, "related_maintenance_visit":items.related_maintenance_visit,
						"sales_order":items.against_sales_order, "installation_time":items.installation_time,
						"prevdoc_docname":source_dn[0].name, "prevdoc_detail_docname":items.name, "prevdoc_doctype": "Delivery Note",
						"customer":source_dn[0].customer, "customer_name":source_dn[0].customer_name,
						"customer_group":source_dn[0].customer_group, "customer_address":source_dn[0].customer_address,
						"address_display":source_dn[0].address_display,
						"territory":source_dn[0].territory, "contact_email":source_dn[0].contact_email,
						"company":source_dn[0].company, "contact_person":source_dn[0].contact_person
						}
				so_items.append(so_x)
			else:
				frappe.throw(_("Serial No {0} in Delivery Note {1} Doesn't Exist.").format(serial_no, items.dn))
	return so_items

@frappe.whitelist()
def get_so_items(sales_order):
	source_items = frappe.db.sql("""select item_code, item_name, description, qty, serial_no, against_sales_order, stock_uom, uom,conversion_factor, parent as dn from `tabDelivery Note Item`
						where docstatus=1 and against_sales_order=%s""", (sales_order), as_dict=1)
	so_items = []
	for items in source_items:
		serial_nos = get_serial_nos(items.serial_no)
		for serial_no in serial_nos:
			if frappe.db.exists("Serial No", serial_no):
				so_x = {"item_code":items.item_code, "item_name":items.item_name, "description":items.description, "qty":1, "serial_no":serial_no,
						"sales_order":items.against_sales_order, "stock_uom":items.stock_uom, "uom":items.uom, "conversion_factor":items.conversion_factor}
				so_items.append(so_x)
			else:
				frappe.throw(_("Serial No {0} in Delivery Note {1} Doesn't Exist.").format(serial_no, items.dn))
	return so_items

@frappe.whitelist()
def get_serial_nos(serial_no):
	return [s.strip() for s in cstr(serial_no).strip().upper().replace(',', '\n').split('\n')
		if s.strip()]

@frappe.whitelist()
def get_so_items_old(source_name, target_doc=None):
	#def set_missing_values(source, target):
	#	#target.ignore_pricing_rule = 1
	#	#target.run_method("set_missing_values")
	#	#target.run_method("calculate_taxes_and_totals")
	def update_item(source, target, source_parent):
		target.rate = 0
		target.base_amount = 0
		target.amount = 0

	target_doc = get_mapped_doc("Sales Order", source_name, {
		"Sales Order": {
			"doctype": "Quotation",
			"field_no_map": [
				"order_type",
				"maintenance_type",
				"additional_discount_percentage",
				"address_display",
				"selling_price_list",
				"campaign",
				"currency",
				"conversion_rate",
				"territory",
				"total",
				"shipping_rule",
				"customer_name",
				"taxes_and_charges",
				"select_print_heading",
				"title",
				"base_total",
				"shipping_address",
				"transaction_date",
				"source",
				"base_grand_total",
				"contact_display",
				"base_in_words",
				"letter_head",
				"tc_name",
				"terms",
				"ignore_pricing_rule",
				"customer_group",
				"company",
				"base_net_total",
				"base_discount_amount",
				"base_rounded_total",
				"base_total_taxes_and_charges",
				"contact_mobile",
				"discount_amount",
				"grand_total",
				"language",
				"customer_address",
				"shipping_address_name",
				"price_list_currency",
				"plc_conversion_rate",
				"apply_discount_on",
				"net_total",
				"status",
				"rounded_total",
				"contact_email",
				"contact_person",
				"in_words",
				"total_taxes_and_charges"
			],
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Sales Order Item": {
			"doctype": "Quotation Item",
			"field_map": {
				"rate": 0,
			},
			"postprocess": update_item,
			"condition": lambda doc: doc.serial_n
		}
	}, target_doc)

	return target_doc

@frappe.whitelist()
def make_maintenance_visit(args):
	if isinstance(args, basestring):
		args = json.loads(args)

	mv = frappe.new_doc("Maintenance Visit")
	mv.type = "Maintenance"
	mv.company = args.get("company")
	mv.customer = args.get("customer")
	mv.customer_name = args.get("customer_name")
	mv.address_display = args.get("address_display")
	mv.contact_display = args.get("contact_display")
	mv.contact_mobile = args.get("contact_mobile")
	mv.contact_email = args.get("contact_email")
	mv.customer_address = args.get("customer_address")
	mv.customer_group = args.get("customer_group")
	mv.territory = args.get("territory")
	mv.contact_person = args.get("contact_person")
	mv.machine_serial_no = args.get("serial_no")
	mv.mntc_date = nowdate()
	mv.sales_order = args.get("sales_order")
	mv.maintenance_contract_type = args.get("maintenance_contract_type")
	mv.completion_status = "Partially Completed"
	mv.maintenance_type = "Scheduled"
	mv.set("purposes", [
		{
			"prevdoc_doctype": "Maintenance Schedule",
			"prevdoc_docname": args.get("name"),
			"prevdoc_detail_docname": args.get("child_name"),
			"work_done": "Not Yet",
			"service_person": args.get("sales_person"),
			"item_code": args.get("item_code"),
			"item_name": args.get("item_name"),
			"description": args.get("description"),
			"serial_no": args.get("serial_no")
		}
	])
	mv.insert(ignore_permissions=True)

	return mv.name

@frappe.whitelist()
def update_maintenance_schedule(name, status):
	doc = frappe.get_doc('Maintenance Visit', name)
	if doc.warranty_claim and status == "Cancel":
		frappe.db.set_value("Warranty Claim", doc.warranty_claim, "engineer_start_time", None)
	if doc.warranty_claim and status == "Submit":
		ref_datetime = "%s %s" % (doc.mntc_date, doc.get("actual_time") or "00:00:00")
		frappe.db.set_value("Warranty Claim", doc.warranty_claim, "engineer_start_time", ref_datetime)

	for d in frappe.get_all('Maintenance Schedule Detail', fields=['name','parent'], filters={"maintenance_visit": ("=", name)}):
		if status == "Cancel":
			frappe.db.set_value("Maintenance Schedule Detail", d.name, "maintenance_visit", None)
			frappe.db.set_value("Maintenance Schedule Detail", d.name, "maintenance_visit_status", None)
			frappe.db.set_value("Maintenance Schedule Detail", d.name, "make_maintenance_visit", None)
			#frappe.get_doc("Maintenance Visit", name).cancel()
		if status == "Submit":
			frappe.db.set_value("Maintenance Schedule Detail", d.name, "maintenance_visit_status", "Submitted")

@frappe.whitelist()
def make_quotation_or_delivery(doc_name):
	qtn_msg = ""
	del_msg = ""
	qtn_list = []
	del_list = []
	qtn_items = []
	del_items = []
	doc = frappe.get_doc('Maintenance Visit', doc_name)

	items_included = frappe.db.sql_list("""select item_category from `tabMaintenance Type Item`
			where parent=%s""", (doc.maintenance_contract_type))
	for item in doc.material_table:
		if item.item_category in items_included:
			# the items are included in maintenance contract so will make delivery note
			del_doc_x = {
				"doctype": "Delivery Note Item",
				"__islocal": 1,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"uom": item.uom,
				"machine_serial_no": item.serial_no,
				"related_maintenance_visit": doc.name,
				"related_sales_order": doc.sales_order,
				"qty": item.qty
				}
			del_items.append(del_doc_x)
		else:
			# the items are not included in maintenance contract so will make quotation
			qtn_doc_x = {
				"doctype": "Quotation Item",
				"__islocal": 1,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"uom": item.uom,
				"machine_serial_no": item.serial_no,
				"related_maintenance_visit": doc.name,
				"related_sales_order": doc.sales_order,
				"qty": item.qty
				}
			qtn_items.append(qtn_doc_x)

	if del_items:
		del_doc = frappe.new_doc("Delivery Note")
		del_doc.naming_series = '_MVD'
		del_doc.posting_date = nowdate()
		del_doc.posting_time = nowtime()
		del_doc.company = doc.company
		del_doc.customer = doc.customer
		del_doc.set("items", del_items)
		del_doc.flags.ignore_permissions = 1
		del_doc.insert()
		del_list.append(del_doc.name)

	if qtn_items:
		qtn_doc = frappe.new_doc("Quotation")
		qtn_doc.naming_series = '_MVQ'
		qtn_doc.quotation_to = "Customer"
		qtn_doc.order_type = "Sales"
		qtn_doc.transaction_date = nowdate()
		qtn_doc.valid_to = add_days(nowdate(), 15)
		qtn_doc.company = doc.company
		qtn_doc.customer = doc.customer
		qtn_doc.set("items", qtn_items)
		qtn_doc.flags.ignore_permissions = 1
		qtn_doc.insert()
		qtn_list.append(qtn_doc.name)

	if del_list:
		del_res = ["""<a href="#Form/Delivery Note/%s" target="_blank">%s</a>""" % \
		(s, s) for s in del_list]
		del_msg = ("Delivery Note {0} created").format(comma_and(del_res))
	if qtn_list:
		qtn_res = ["""<a href="#Form/Quotation/%s" target="_blank">%s</a>""" % \
		(s, s) for s in qtn_list]
		qtn_msg = ("Quotation {0} created").format(comma_and(qtn_res))
	g_msg = qtn_msg + "\n\n" + del_msg
	#frappe.db.set_value("Material Table", doc_name, "reserved", 1)

	frappe.msgprint(g_msg)

@frappe.whitelist()
def mv_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select name from `tabMaintenance Visit`
					where docstatus=1 and not name in (select related_maintenance_visit from `tabSales Invoice Item` where docstatus<2)
					and with_cost=%(with_cost)s
					and ({key} like %(txt)s)
					{mcond}
					order by
						if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
						name
					limit %(start)s, %(page_len)s""".format(**{
						'key': searchfield,
						'mcond':get_match_cond(doctype)
					}), {
						'txt': "%%%s%%" % txt,
						'_txt': txt.replace("%", ""),
						'start': start,
						'page_len': page_len,
						'with_cost': filters.get('with_cost')
					})

@frappe.whitelist()
def update_sn_from_ms(doc, flg):
	doc = frappe.get_doc(json.loads(doc))
	#doc = frappe.get_doc('Maintenance Schedule', doc_name)
	if flg == 'Submit':
		for item in doc.items:
			if item.serial_no:
				frappe.db.set_value("Serial No", item.serial_no, "maintenance_contract_type", doc.maintenance_contract_type)
				frappe.db.set_value("Serial No", item.serial_no, "amc_start_date", item.start_date)
				frappe.db.set_value("Serial No", item.serial_no, "amc_expiry_date", item.end_date)
	if flg == 'Cancel':
		for item in doc.items:
			if item.serial_no:
				frappe.db.set_value("Serial No", item.serial_no, "maintenance_contract_type", None)
				frappe.db.set_value("Serial No", item.serial_no, "amc_start_date", None)
				frappe.db.set_value("Serial No", item.serial_no, "amc_expiry_date", None)

@frappe.whitelist()
def update_sn_from_dn(doc_name):
	doc = frappe.get_doc('Delivery Note', doc_name)

	for item in doc.items:
		sdoc = frappe.get_doc('Sales Order', item.against_sales_order)
		if item.serial_no and item.against_sales_order:
			serial_nos = get_serial_nos(item.serial_no)
			for serial_no in serial_nos:
				frappe.db.set_value("Serial No", serial_no, "sales_type", sdoc.sales_type)
				frappe.db.set_value("Serial No", serial_no, "maintenance_contract_type", sdoc.maintenance_contract_type)
				frappe.db.set_value("Serial No", serial_no, "customer", sdoc.customer)
				frappe.db.set_value("Serial No", serial_no, "customer_name", sdoc.customer_name)
				frappe.db.set_value("Serial No", serial_no, "contract_start_date", sdoc.contract_start_date)
				frappe.db.set_value("Serial No", serial_no, "contract_end_date", sdoc.contract_end_date)

@frappe.whitelist()
def create_invoices(company, year, month):
	items_to_be_invoiced = frappe.db.sql("""select company, customer, sales_order, extra_copies_bills_are_issued_each, count(*) as cnt,
								sum(total_extra_copies_bw_a4) as extra_copies_bw_a4, sum(total_extra_copies_bw_a4*extra_copies_charges_bw_a4) as total_charge_bw_a4,
								sum(total_extra_copies_bw_a3) as extra_copies_bw_a3, sum(total_extra_copies_bw_a3*extra_copies_charges_bw_a3) as total_charge_bw_a3,
								sum(total_extra_copies_color_a4) as extra_copies_color_a4, sum(total_extra_copies_color_a4*extra_copies_charges_color_a4) as total_charge_color_a4,
								sum(total_extra_copies_color_a3) as extra_copies_color_a3, sum(total_extra_copies_color_a3*extra_copies_charges_color_a3) as total_charge_color_a3
								from `tabAccount extra copies`
								where docstatus=1 and isnull(sales_invoice) and year=%(year)s and month<=%(month)s and company=%(company)s
								group by sales_order having extra_copies_bills_are_issued_each<=count(*)
								and (extra_copies_bw_a4+extra_copies_bw_a3+extra_copies_color_a4+extra_copies_color_a3)>0
								""", {'year': year, 'month': month, 'company': company}, as_dict=True)


	invoices_list = []
	month_last_day = get_last_day(getdate(year + '-' + month + '-' + '01'))
	price_list = (frappe.db.get_single_value('Selling Settings', 'selling_price_list')
			or frappe.db.get_value('Price List', _('Standard Selling')))

	if items_to_be_invoiced:
		#company_currency = frappe.db.get_value("Company", items_to_be_invoiced[0].company, "default_currency")
		company_doc = frappe.get_doc('Company', company)
		for item in items_to_be_invoiced:
			sales_invoice = frappe.new_doc("Sales Invoice")
			sales_invoice.update({
				"posting_date": month_last_day,
				"due_date": nowdate() if getdate(nowdate()) > getdate(month_last_day) else month_last_day,
				"customer": item.customer,
				"status": "Draft",
				"company": company,
				"selling_price_list": price_list,
				"extra_copies": 1
			})

			if item.total_charge_bw_a4 > 0:
				sales_invoice.append("items", {
					"doctype": "Sales Invoice Item",
					"item_name": 'Extra Copies B/W',
					"description": 'Extra Copies B/W',
					"uom": 'Unit',
					"stock_uom": 'Unit',
					"conversion_factor": 1,
					"qty": item.extra_copies_bw_a4,
					"rate": item.total_charge_bw_a4 / item.extra_copies_bw_a4,
					"income_account": company_doc.extra_copies_account,
					"cost_center": company_doc.cost_center
				})
			if item.total_charge_color_a4 > 0:
				sales_invoice.append("items", {
					"doctype": "Sales Invoice Item",
					"item_name": 'Extra Copies Color',
					"description": 'Extra Copies Color',
					"uom": 'Unit',
					"stock_uom": 'Unit',
					"conversion_factor": 1,
					"qty": item.extra_copies_color_a4,
					"rate": item.total_charge_color_a4 / item.extra_copies_color_a4,
					"income_account": company_doc.extra_copies_account,
					"cost_center": company_doc.cost_center
				})
			if item.total_charge_bw_a3 > 0:
				sales_invoice.append("items", {
					"doctype": "Sales Invoice Item",
					"item_name": 'Extra Copies B/W A3',
					"description": 'Extra Copies B/W A3',
					"uom": 'Unit',
					"stock_uom": 'Unit',
					"conversion_factor": 1,
					"qty": item.extra_copies_bw_a3,
					"rate": item.total_charge_bw_a3 / item.extra_copies_bw_a3,
					"income_account": company_doc.extra_copies_account,
					"cost_center": company_doc.cost_center
				})
			if item.total_charge_color_a3 > 0:
				sales_invoice.append("items", {
					"doctype": "Sales Invoice Item",
					"item_name": 'Extra Copies Color A3',
					"description": 'Extra Copies Color A3',
					"uom": 'Unit',
					"stock_uom": 'Unit',
					"conversion_factor": 1,
					"qty": item.extra_copies_color_a3,
					"rate": item.total_charge_color_a3 / item.extra_copies_color_a3,
					"income_account": company_doc.extra_copies_account,
					"cost_center": company_doc.cost_center
				})

			sales_invoice.flags.ignore_permissions = 1
			try:
				sales_invoice.insert()
				#sales_invoice.submit()
				frappe.db.sql("""update `tabAccount extra copies` set sales_invoice=%(sales_invoice)s
								where docstatus=1 and isnull(sales_invoice) and year=%(year)s and month<=%(month)s and company=%(company)s
								and sales_order=%(sales_order)s and extra_copies_bills_are_issued_each<=%(cnt)s""",
								{'year': year, 'month': month, 'company': company, 'cnt': item.cnt,
								'sales_order': item.sales_order, 'sales_invoice': sales_invoice.name})
				frappe.db.commit()
				invoices_list.append(sales_invoice.name)
			except Exception:
				msgprint(_("Error while Creating Invoice at so number ")+item.sales_order)

		if invoices_list:
			message = ["""<a href="#Form/Sales Invoice/%s" target="_blank">%s</a>""" % \
				(p, p) for p in invoices_list]
			msgprint(_("Sales Invoices {0} created").format(comma_and(message)))
	else:
		msgprint(_("Nothing to Invoice"))

@frappe.whitelist()
def submit_invoices(company, year, month):
	items_to_be_submitted = frappe.db.sql("""select name from `tabSales Invoice`
								where docstatus=0 and extra_copies=1 and company=%(company)s
								""", {'company': company}, as_dict=True)

	invoices_list = []

	if items_to_be_submitted:
		for item in items_to_be_submitted:
			sales_invoice = frappe.get_doc("Sales Invoice", item.name)
			sales_invoice.flags.ignore_permissions = 1
			try:
				sales_invoice.submit()
				invoices_list.append(sales_invoice.name)
			except:
				msgprint(_("Error while Submitting Invoice  ")+sales_invoice.name)

		if invoices_list:
			message = ["""<a href="#Form/Sales Invoice/%s" target="_blank">%s</a>""" % \
				(p, p) for p in invoices_list]
			msgprint(_("Sales Invoices {0} submitted").format(comma_and(message)))
	else:
		msgprint(_("Nothing to Submit"))

@frappe.whitelist()
def dn_make_stock_entry(delivery_note, purpose):
	"""Make a new Stock Entry from Deleviery Note"""

	delivery_note = frappe.get_doc('Delivery Note', delivery_note)

	items = []
	for item in delivery_note.items:
		items.append({
			'actual_qty': item.actual_qty,
			'allow_zero_valuation_rate': item.allow_zero_valuation_rate,
			'amount': item.amount,
			'barcode': item.barcode,
			'batch_no': item.batch_no,
			'conversion_factor': item.conversion_factor,
			'cost_center': item.cost_center,
			'description': item.description,
			'expense_account': item.expense_account,
			'image': item.image,
			'item_code': item.item_code,
			'item_name': item.item_name,
			'qty': item.qty,
			's_warehouse': item.target_warehouse,
			'serial_no': item.serial_no,
			'stock_uom': item.stock_uom,
			't_warehouse': 'Used - KPS',
			'uom': item.uom,
		})

	stock_entry = frappe.new_doc('Stock Entry')
	stock_entry.purpose = purpose
	stock_entry.set('items', items)

	return stock_entry.as_dict()

@frappe.whitelist()
def update_sn_from_dn_to_so_old(dn):
	"""Update serial number from Delivery Note to Sales Order"""

	dn = frappe.get_doc("Delivery Note", dn)
	dn_items = [item for item in dn.items if item.so_detail and item.serial_no]
	dn_items.sort(key=lambda item: item.against_sales_order)

	for i, dn_item in enumerate(dn_items):
		if i == 0 or dn_items[i].against_sales_order != dn_items[i - 1].against_sales_order:
			so = frappe.get_doc("Sales Order", dn_item.against_sales_order)

		for so_item in so.items:
			if so_item.name == dn_item.so_detail:
				so_item.serial_n = dn_item.serial_no.split()[0]
				break

		if i == len(dn_items) - 1 or dn_items[i].against_sales_order != dn_items[i + 1].against_sales_order:
			so.save()

@frappe.whitelist()
def update_sn_from_dn_to_so(dn):
	"""Update serial number from Delivery Note to Sales Order"""

	dn = frappe.get_doc("Delivery Note", dn)
	dn_items = [item for item in dn.items if item.so_detail and item.serial_no]
	dn_items.sort(key=lambda item: item.against_sales_order)

	for i, dn_item in enumerate(dn_items):
		if dn_item.so_detail:
			frappe.db.set_value("Sales Order Item", dn_item.so_detail, "serial_n", dn_item.serial_no.split()[0])

@frappe.whitelist()
def get_dn_from_in(delivery_note):
	"""Get Delivery Note from Installation Note"""
	source_dn = frappe.db.sql("""select * from `tabDelivery Note`
						where docstatus=1 and name=%s""", (delivery_note), as_dict=1)
	source_items = frappe.db.sql("""select dni.item_code, dni.item_name, dni.description, dni.qty, dni.serial_no, dni.against_sales_order, dni.related_maintenance_visit,
						dni.stock_uom, dni.parent as dn, dni.name, dni.machine_serial_no, i.installation_time from `tabDelivery Note Item` dni
						left join `tabItem` i on i.name=dni.item_code
						where dni.docstatus=1 and dni.parent=%s""", (delivery_note), as_dict=1)
	so_items = []
	for items in source_items:
		is_stock_item = frappe.db.get_value("Item", {"name": items.item_code}, "is_stock_item")
		if is_stock_item:
			serial_nos = get_serial_nos(items.serial_no)
			if not serial_nos: serial_nos = [""]
			for serial_no in serial_nos:
				so_x = {"item_code":items.item_code, "item_name":items.item_name, "machine_serial_no":items.machine_serial_no, "qty": 1 if serial_no else items.qty,
						"serial_no":items.serial_no, "serial_n":items.serial_no, "related_maintenance_visit":items.related_maintenance_visit,
						"sales_order":items.against_sales_order, "installation_time":items.installation_time,
						"prevdoc_docname":source_dn[0].name, "prevdoc_detail_docname":items.name, "prevdoc_doctype": "Delivery Note",
						"customer":source_dn[0].customer, "customer_name":source_dn[0].customer_name,
						"customer_group":source_dn[0].customer_group, "customer_address":source_dn[0].customer_address,
						"address_display":source_dn[0].address_display,
						"territory":source_dn[0].territory, "contact_email":source_dn[0].contact_email,
						"company":source_dn[0].company, "contact_person":source_dn[0].contact_person
						}
				so_items.append(so_x)
	return so_items
