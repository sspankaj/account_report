# -*- coding: utf-8 -*-
##############################################################################
#
#    Cubic ERP, Enterprise and Government Management Software
#    Copyright (C) 2017 Cubic ERP S.A.C. (<http://cubicerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, models, _
from odoo.tools import float_repr
import json


rec = 0
def autoIncrement():
    global rec
    pStart = 1
    pInterval = 1
    if rec == 0:
        rec = pStart
    else:
        rec += pInterval
    return rec


class AccountReportLedger(models.TransientModel):
    _name = 'account.report.ledger'

    def convert_lines(self, data, model=False, model_id=0, parent_id=None, level=1):
        res = []
        company = self._context.get('company_id') and self.env['res.company'].browse(self._context.get('company_id')[0]) or self.env.user.company_id
        if model and model_id:
            for d in data:
                for m in d['move_lines']:
                    r = {'id': autoIncrement(),
                         'model': model,
                         'model_id': model_id,
                         'unfoldable': False,
                         'parent_id': parent_id,
                         'level': level,
                         'type': 'line',
                         'res_model': 'account.move.line',
                         'res_id': m['lid'],
                         'reference': m['move_name'],
                         'columns': [m['move_name'],
                                     m['ldate'],
                                     m['lcode'],
                                     m['partner_name'],
                                     "%s%s" % (m['lname'], m.get('lref') and " - %s" % m['lref'] or ''),
                                     m['debit'],
                                     m['credit'],
                                     m['balance'],
                                     m['amount_currency'] and "%s %s"%(m['currency_code'],float_repr(m['amount_currency'],company.currency_id.decimal_places)) or company.currency_id.symbol,
                                     ]
                         }
                    res.append(r)
        else:
            total = [(_('Undistributed profit'),"white-space: nowrap;text-align: right;font-weight: normal;font-style: italic;"),0.0,0.0,0.0,company.currency_id.symbol or '']
            for d in data:
                r = {'id': autoIncrement(),
                     'model': model or 'account.account',
                     'model_id': model_id or d.get('account_id'),
                     'unfoldable': False if model else bool(d.get('move_lines')),
                     'parent_id': parent_id,
                     'level': level,
                     'type': 'line',
                     'columns' : ["%s %s"%(d['code'],d['name']),
                                  d['debit'],
                                  d['credit'],
                                  d['balance'],
                                  company.currency_id.symbol or '',
                                  ]
                     }
                res.append(r)
                total[3] += d['balance']
            if total[3]:
                total[1] = (float_repr(total[3] > 0.0 and total[3] or 0.0, company.currency_id.decimal_places),"white-space: nowrap;text-align: right;font-weight: normal;font-style: italic;")
                total[2] = (float_repr(total[3] < 0.0 and (-1.0 * total[3]) or 0.0, company.currency_id.decimal_places),"white-space: nowrap;text-align: right;font-weight: normal;font-style: italic;")
                total[3] = (float_repr(total[3], company.currency_id.decimal_places),"white-space: nowrap;text-align: right;font-weight: normal;font-style: italic;")
                res.append({
                    'id': autoIncrement(),
                    'model': model or 'account.account',
                    'model_id': 0,
                    'unfoldable': False,
                    'parent_id': 0,
                    'level': level,
                    'type': 'line',
                    'columns': total,
                })
        return res

    @api.model
    def get_lines(self, line_id=None, **kw):
        form = dict(self.env.context)
        model = False
        model_id = False
        level = 1
        if kw:
            level = kw['level']
            model = kw['model_name']
            model_id = kw['model_id']
            form = kw['form']

        accounts = self.env['account.account'].browse(model_id) if model == 'account.account' else self.env['account.account'].search([])
        res = self.env['report.account.report_generalledger'].with_context(form.get('used_context', {}))._get_account_move_entry(accounts,
                                                                                                       form.get('initial_balance'),
                                                                                                       form.get('sortby'),
                                                                                                       form.get('display_account'))

        return self.convert_lines(res, model=model, model_id=model_id, parent_id=line_id, level=level)

    def _get_html(self):
        result = {}
        rcontext = {}
        form = dict(self.env.context)
        company = form.get('company_id') and self.env['res.company'].browse(form.get('company_id')[0]) or self.env.user.company_id
        rcontext['lines'] = self.with_context(form).get_lines()
        rcontext['print_journal'] = [j.code for j in self.env['account.journal'].browse(form.get('journal_ids',[]))]
        rcontext['company'] = company.name
        form['decimal_places'] = company.currency_id.decimal_places
        form['report_name'] = 'account.report_generalledger'
        form['active_model'] = 'account.report.general.ledger'
        form['active_id'] = self.env.ref('account.action_report_general_ledger').id
        rcontext['data'] = form
        rcontext['form'] = json.dumps(form)
        result['html'] = self.env.ref('account_report.report_account_ledger').render(rcontext)
        return result

    @api.model
    def get_html(self, data=None):
        res = self.search([('create_uid', '=', self.env.uid)], limit=1)
        if not res:
            return self.create({}).with_context(data.get('form',{}))._get_html()
        return res.with_context(data.get('form',{}))._get_html()


class ReportGeneralLedgerNew(models.AbstractModel):          
    _inherit = 'report.account.report_generalledger'
    def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
        """
        :param:
                accounts: the recordset of accounts
                init_balance: boolean value of initial_balance
                sortby: sorting by date or partner and journal
                display_account: type of account(receivable, payable and both)

        Returns a dictionary of accounts with following key and value {
                'code': account code,
                'name': account name,
                'debit': sum of total debit amount,
                'credit': sum of total credit amount,
                'balance': total balance,
                'amount_currency': sum of amount_currency,
                'move_lines': list of move line
        }
        """
        cr = self.env.cr
        MoveLine = self.env['account.move.line']
        move_lines = {x: [] for x in accounts.ids}

        # Prepare initial sql query and Get the initial move lines
        if init_balance:
            init_tables, init_where_clause, init_where_params = MoveLine.with_context(date_from=self.env.context.get('date_from'), date_to=False, initial_bal=True)._query_get()
            init_wheres = [""]
            if init_where_clause.strip():
                init_wheres.append(init_where_clause.strip())
            init_filters = " AND ".join(init_wheres)
            filters = init_filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
            sql = ("""SELECT 0 AS lid, l.account_id AS account_id, '' AS ldate, '' AS lcode, NULL AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance, '' AS lpartner_id,\
                '' AS move_name, '' AS mmove_id, '' AS currency_code,\
                NULL AS currency_id,\
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,\
                '' AS partner_name\
                FROM account_move_line l\
                LEFT JOIN account_move m ON (l.move_id=m.id)\
                LEFT JOIN res_currency c ON (l.currency_id=c.id)\
                LEFT JOIN res_partner p ON (l.partner_id=p.id)\
                LEFT JOIN account_invoice i ON (m.id =i.move_id)\
                JOIN account_journal j ON (l.journal_id=j.id)\
                WHERE l.account_id IN %s""" + filters + ' GROUP BY l.account_id')
            params = (tuple(accounts.ids),) + tuple(init_where_params)
            cr.execute(sql, params)
            for row in cr.dictfetchall():
                move_lines[row.pop('account_id')].append(row)

        sql_sort = 'l.date, l.move_id'
        if sortby == 'sort_journal_partner':
            sql_sort = 'j.code, p.name, l.move_id'

        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql = ('''SELECT l.id AS lid, l.account_id AS account_id, l.date AS ldate, j.code AS lcode, l.currency_id, l.amount_currency, l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,\
            m.name AS move_name, c.symbol AS currency_code, p.name AS partner_name\
            FROM account_move_line l\
            JOIN account_move m ON (l.move_id=m.id)\
            LEFT JOIN res_currency c ON (l.currency_id=c.id)\
            LEFT JOIN res_partner p ON (l.partner_id=p.id)\
            JOIN account_journal j ON (l.journal_id=j.id)\
            JOIN account_account acc ON (l.account_id = acc.id) \
            WHERE l.account_id IN %s ''' + filters + ''' GROUP BY l.id, l.account_id, l.date, j.code, l.currency_id, l.amount_currency, l.ref, l.name, m.name, c.symbol, p.name ORDER BY ''' + sql_sort)
        params = (tuple(accounts.ids),) + tuple(where_params)
        cr.execute(sql, params)

        for row in cr.dictfetchall():
            balance = 0
            for line in move_lines.get(row['account_id']):
                balance += line['debit'] - line['credit']
            row['balance'] += balance
            move_lines[row.pop('account_id')].append(row)

        # Calculate the debit, credit and balance for Accounts
        account_res = []
        for account in accounts:
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
            res['code'] = account.code
            res['name'] = account.name
            res['account_id']=account.id
            res['move_lines'] = move_lines[account.id]
            for line in res.get('move_lines'):
                res['debit'] += line['debit']
                res['credit'] += line['credit']
                res['balance'] = line['balance']   
            if display_account == 'all':
                account_res.append(res)
            if display_account == 'movement' and res.get('move_lines'):
                account_res.append(res)
            if display_account == 'not_zero' and not currency.is_zero(res['balance']):
                account_res.append(res)
            
             
        return account_res
  