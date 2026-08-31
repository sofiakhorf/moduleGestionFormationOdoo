from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
import pytz


class FormationRoom(models.Model):
    _name = 'formation.room'
    _description = 'Salle de Formation'

    name = fields.Char(string="Nom de la salle", required=True)
    capacity = fields.Integer(string="Capacité (Places)", required=True)
    location = fields.Char(string="Emplacement / Bâtiment")

    admin_state = fields.Selection([
        ('active', 'Active'),
        ('maintenance', 'En Travaux / Maintenance'),
        ('archived', 'Désactivée')
    ], string="Statut administratif", default='active', required=True)

    is_occupied_now = fields.Boolean(
        string="Occupée actuellement",
        compute='_compute_is_occupied_now',
        help="Calculé à la volée : True si une séance est en cours dans cette salle en ce moment."
    )

    seance_ids = fields.One2many('formation.seance', 'room_id', string="Séances programmées")

    seances_count = fields.Integer(
        string="Nombre de Sessions",
        compute="_compute_seances_count",
        store=True
    )

    @api.depends('seance_ids')
    def _compute_seances_count(self):
        for room in self:
            room.seances_count = len(room.seance_ids)

    def _compute_is_occupied_now(self):
        """ Calculé à la volée à chaque lecture : plus de CRON ni de stockage. """
        user_tz = self.env.user.tz or 'Africa/Algiers'
        local_tz = pytz.timezone(user_tz)
        now = datetime.now(local_tz)
        current_date = now.date()
        current_hour_float = now.hour + (now.minute / 60.0)

        for room in self:
            ongoing_seance = self.env['formation.seance'].search([
                ('room_id', '=', room.id),
                ('date_day', '=', current_date),
                ('start_hour', '<=', current_hour_float),
                ('end_hour', '>', current_hour_float),
                ('session_id.state', 'in', ['confirmed', 'in_progress'])
            ], limit=1)
            room.is_occupied_now = bool(ongoing_seance)

    @api.constrains('capacity')
    def _check_capacity_positive(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError("La capacité de la salle doit être supérieure à zéro.")

    @api.constrains('admin_state')
    def _check_admin_state_change_rules(self):
        for room in self:
            if room.admin_state in ['maintenance', 'archived']:
                active_seances = self.env['formation.seance'].search([
                    ('room_id', '=', room.id),
                    ('date_day', '>=', fields.Date.today()),
                    ('session_id.state', 'not in', ['cancelled'])
                ])
                if active_seances:
                    action = "désactiver" if room.admin_state == 'archived' else "mettre en maintenance"
                    raise ValidationError(
                        f"Impossible de {action} la salle '{room.name}'. "
                        f"Il y a {len(active_seances)} séance(s) programmée(s) actuellement."
                    )

    # -- _update_room_availability() : SUPPRIMÉE, plus besoin de CRON --
    # -- write() : SUPPRIMÉE, plus besoin de protection manuelle --