# -*- coding: utf-8 -*-
# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, today, getdate, nowtime

def post_depreciation_entries(date=None):
	if not date:
		date = today()
	for asset in get_depreciable_assets(date):
		make_depreciation_entry(asset, date)
		frappe.db.commit()

def get_depreciable_assets(date):
	return frappe.db.sql_list("""select a.name
		from tabAsset a
		left join `tabDepreciation Schedule` ds on a.name = ds.parent
		left join `tabItem` i on a.item_code=i.name
		where a.docstatus=1 and ds.schedule_date<=%s
			and a.status in ('Submitted', 'Partially Depreciated')
			and i.is_fixed_asset<>1
			and ifnull(ds.stock_reconciliation, '')=''
			Order by ds.schedule_date""", date)

@frappe.whitelist()
def make_depreciation_entry(asset_name, date=None):
	frappe.has_permission('Stock Reconciliation', throw=True)
	
	if not date:
		date = today()

	asset = frappe.get_doc("Asset", asset_name)
	if asset.is_fixed_asset == 1:
		return
	fixed_asset_account, accumulated_depreciation_account, depreciation_expense_account = \
		get_depreciation_accounts(asset)

	depreciation_cost_center = frappe.db.get_value("Company", asset.company, "depreciation_cost_center")
	
	for d in asset.get("schedules"):
		if not d.stock_reconciliation and getdate(d.schedule_date) <= getdate(date):
			sle = get_stock_ledger_entries(asset.item_code, asset.warehouse, d.schedule_date)
			if sle:
				sr = frappe.new_doc("Stock Reconciliation")
				sr.naming_series = "_SR/"
				#sr.expense_account = accumulated_depreciation_account
				sr.expense_account = depreciation_expense_account
				sr.cost_center = depreciation_cost_center
				sr.posting_date = d.schedule_date
				sr.posting_time = nowtime()
				sr.company = asset.company
				sr.is_depreciation = 1
				sr.serial_no = asset.serial_no

				sr.append("items", {
					"item_code": asset.item_code,
					"warehouse": asset.warehouse,
					"qty": sle[0].qty_after_transaction,
					"valuation_rate": flt(sle[0].valuation_rate) - (flt(d.depreciation_amount) / flt(sle[0].qty_after_transaction))
				})

				sr.flags.ignore_permissions = True
				sr.submit()

				d.db_set("stock_reconciliation", sr.name)
				asset.value_after_depreciation -= d.depreciation_amount

	asset.db_set("value_after_depreciation", asset.value_after_depreciation)
	asset.set_status()

	return asset

def get_depreciation_accounts(asset):
	fixed_asset_account = accumulated_depreciation_account = depreciation_expense_account = None
	
	accounts = frappe.db.get_value("Asset Category Account",
		filters={'parent': asset.asset_category, 'company_name': asset.company},
		fieldname = ['fixed_asset_account', 'accumulated_depreciation_account',
			'depreciation_expense_account'], as_dict=1)

	if accounts:	
		fixed_asset_account = accounts.fixed_asset_account
		accumulated_depreciation_account = accounts.accumulated_depreciation_account
		depreciation_expense_account = accounts.depreciation_expense_account
		
	if not accumulated_depreciation_account or not depreciation_expense_account:
		accounts = frappe.db.get_value("Company", asset.company,
			["accumulated_depreciation_account", "depreciation_expense_account"])
		
		if not accumulated_depreciation_account:
			accumulated_depreciation_account = accounts[0]
		if not depreciation_expense_account:
			depreciation_expense_account = accounts[1]

	if not fixed_asset_account or not accumulated_depreciation_account or not depreciation_expense_account:
		frappe.throw(_("Please set Depreciation related Accounts in Asset Category {0} or Company {1}")
			.format(asset.asset_category, asset.company))

	return fixed_asset_account, accumulated_depreciation_account, depreciation_expense_account

def get_stock_ledger_entries(item_code, warehouse, posting_date):
	return frappe.db.sql("""select qty_after_transaction, valuation_rate 
		from `tabStock Ledger Entry` sle force index (posting_sort_index)
		where docstatus < 2 and item_code=%s and warehouse=%s and posting_date<=%s
		order by posting_date DESC, posting_time DESC, name DESC Limit 1""", (item_code, warehouse, posting_date), as_dict=1)
