from odoo import models, fields, api
from odoo.exceptions import ValidationError




class FormationAttendance(models.Model):
    _name = 'formation.attendance'
    _description = 'Association Posséde (Présences)'

    seance_id = fields.Many2one('formation.seance', string="Séance", required=True)
    registration_id = fields.Many2one(
        'formation.registration', string="Inscription",
        required=True, ondelete='cascade'
    )
    # partner_id devient dérivé au lieu d'être saisi séparément
    partner_id = fields.Many2one(
        related='registration_id.partner_id', store=True, string="Participant"
    )

    # Attribut porté par l'association 'posséde'
    attendance_status = fields.Selection([
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'En retard')
    ], string="Statut Présence", default='present')

    # On ajoute la date de la séance en champ lié (related) pour faciliter les recherches/filtres
    # Champ lié pour l'affichage et les filtres
    date_day = fields.Date(related='seance_id.date_day', store=True, string="Date Séance")






    @api.model_create_multi
    def create(self, vals_list):
        attendances = super().create(vals_list)
        attendances.registration_id._notify_if_absence_threshold_crossed()
        return attendances

    def write(self, vals):
        if 'attendance_status' not in vals:
            return super().write(vals)

        # Snapshot AVANT modification : seul moyen de savoir si on franchit le seuil
        registrations = self.registration_id
        previous_state = {r.id: r.proposed_cancellation for r in registrations}

        res = super().write(vals)

        registrations._notify_if_absence_threshold_crossed(previous_state)
        return res

    _sql_constraints = [
        ('uniq_seance_registration', 'unique(seance_id, registration_id)',
         "Une ligne de présence existe déjà pour cette inscription sur cette séance.")
    ]





