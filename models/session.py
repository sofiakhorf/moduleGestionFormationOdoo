from odoo import models, fields, api
from datetime import date, timedelta
from odoo.exceptions import ValidationError

class FormationSession(models.Model):
    _name = 'formation.session'
    _inherit = [ 'formation.notification.mixin']
    _description = 'Session'

    # =========================================================================
    # 1. CHAMPS & RELATIONS
    # =========================================================================
    name = fields.Char("Nom de la Session", required=True)
    date_start = fields.Date("Date Début")
    date_end = fields.Date("Date Fin")
    seats = fields.Integer("Nombre de places", store=True)
    attendance_threshold = fields.Float(string="Seuil de présence (%)", default=80.0)
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('postponed', 'Reportée'),
        ('done', 'Terminée'),
        ('cancelled', 'Annulée'),
    ], string="Statut", default='draft', tracking=True)

    # Relations Many2one
    course_id = fields.Many2one('formation.course', string="Formation", required=True)
    instructor_id = fields.Many2one(
        'res.partner', 
        string="Formateur",
        domain="[('is_instructor', '=', True), ('id', 'in', instructor_eligible_ids)]"
    )

    # Relations One2many
    registration_ids = fields.One2many('formation.registration', 'session_id', string="Inscriptions")
    seance_ids = fields.One2many('formation.seance', 'session_id', string="Séances")

    # Champs techniques et calculés
    instructor_eligible_ids = fields.Many2many(
        'res.partner', 
        compute='_compute_instructor_eligible_ids'
    )
    duration_total = fields.Float(string="Durée Totale (Heures)", compute='_compute_duration_total', store=True)
    room_ids = fields.Many2many(
        'formation.room', 
        string="Salles utilisées", 
        compute='_compute_room_ids'
    )

    # =========================================================================
    # 2. MÉTHODES CALCULÉES (@api.depends)
    # =========================================================================
    @api.depends('course_id')
    def _compute_instructor_eligible_ids(self):
        for session in self:
            if session.course_id:
                session.instructor_eligible_ids = session.course_id.instructor_ids
            else:
                session.instructor_eligible_ids = self.env['res.partner'].browse()

    @api.depends('seance_ids.start_hour', 'seance_ids.end_hour')
    def _compute_duration_total(self):
        for session in self:
            session.duration_total = sum(s.end_hour - s.start_hour for s in session.seance_ids)

    @api.depends('seance_ids.room_id')
    def _compute_room_ids(self):
        for session in self:
            session.room_ids = session.seance_ids.mapped('room_id')

    # =========================================================================
    # 3. CONTRAINTES DE VALIDATION (@api.constrains)
    # =========================================================================
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError("La date de fin ne peut pas être antérieure à la date de début !")

    @api.constrains('seats', 'registration_ids')
    def _check_seats_limit(self):
        for record in self:
            if record.seats > 0 and len(record.registration_ids) > record.seats:
                raise ValidationError(
                    f"Surréservation ! Le nombre de participants actuels ({len(record.registration_ids)}) "
                    f"dépasse le nombre de places maximum autorisé ({record.seats}) pour cette session."
                )

    @api.constrains('state')
    def _check_requirements_on_state_change(self):
        for session in self:
            if session.state in ['confirmed', 'in_progress']:
                if not session.date_start or not session.date_end:
                    raise ValidationError("Impossible de confirmer : Les dates de début et de fin doivent être renseignées.")
                for seance in session.seance_ids:
                    seance._check_seance_constraints()

    # =========================================================================
    # 4. MÉTHODES MÉTIER & CERVEAU DES STATUTS
    # =========================================================================
    def _apply_state_logic(self):
        today = fields.Date.today()
        for record in self:
            if not record.date_start:
                continue

            if record.state == 'draft':
                if record.date_start == today + timedelta(days=1):
                    record.notify_admin("Alerte J-1 : Session toujours en Brouillon.")
                elif record.date_start <= today:
                    record.notify_admin("URGENT : Date de début atteinte (Session en Brouillon).")

            new_state = False
            if record.state == 'confirmed' and record.date_start <= today:
                new_state = 'in_progress'
            elif record.state == 'in_progress' and record.date_end and record.date_end < today:
                new_state = 'done'
            elif record.state == 'in_progress' and record.date_start > today:
                new_state = 'confirmed'

            if new_state:
                record.state = new_state
                return new_state

    def action_notify_missing_evaluations(self):
        for session in self:
            students_without_eval = session.registration_ids.filtered(
                lambda r: (r.evaluation == 0.0 or not r.evaluation) and r.status == 'registered'
            )
            if students_without_eval:
                session.notify_admin(
                    f"Alerte : Évaluations manquantes pour {len(students_without_eval)} "
                    f"participants inscrits dans la session {session.name}"
                )

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_postpone(self):
        self.write({'state': 'postponed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_in_progress(self):
        for record in self:
            record.write({'state': 'in_progress'})

    def action_done(self):
        for record in self:
            record.write({'state': 'done'})

    # =========================================================================
    # 5. SURCHARGE DES MÉTHODES ORM (CRUD & CRON)
    # =========================================================================
    def write(self, vals):
        res = super(FormationSession, self).write(vals)
        if 'date_start' in vals or 'date_end' in vals or 'state' in vals:
            for record in self:
                changed_state = record._apply_state_logic()
                message = "Dates mises à jour."
                if changed_state:
                    message = f"Statut mis à jour : {record.state}"
                elif record.state == 'draft':
                    message = "Vérification des alertes effectuée (J-1)."

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Système de Formation',
                        'message': message,
                        'sticky': False,
                        'type': 'success',
                    }
                }
        return res

    @api.model
    def _scheduler_check_sessions(self):
        sessions = self.search([('state', 'not in', [ 'cancelled'])])
        sessions._apply_state_logic()