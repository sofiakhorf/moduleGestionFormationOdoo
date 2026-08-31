from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FormationSeance(models.Model):
    _name = 'formation.seance'
    _description = 'Séance'

    # =========================================================================
    # 1. CHAMPS & RELATIONS
    # =========================================================================
    date_day = fields.Date("Date du jour", required=True)
    start_hour = fields.Float("Heure Début", required=True)
    end_hour = fields.Float("Heure Fin", required=True)

    session_id = fields.Many2one('formation.session', string="Session", required=True)
    room_id = fields.Many2one('formation.room', string="Salle", required=True)
    attendance_ids = fields.One2many('formation.attendance', 'seance_id', string="Feuille d'appel")

    duration = fields.Float(
        string="Durée (Heures)", 
        compute="_compute_duration", 
        store=True, 
        help="Calculé automatiquement : Heure de fin - Heure de début"
    )
    occupation_percent = fields.Integer(
        string="Présents", 
        compute="_occupation_percent_count", 
        store=True
    )
    unavailable_room_ids = fields.Many2many(
        'formation.room',
        compute='_compute_unavailable_rooms',
        string="Salles indisponibles"
    )

    # =========================================================================
    # 2. MÉTHODES CALCULÉES (@api.depends)
    # =========================================================================
    @api.depends('start_hour', 'end_hour')
    def _compute_duration(self):
        for record in self:
            if record.start_hour and record.end_hour:
                diff = record.end_hour - record.start_hour
                record.duration = diff if diff > 0 else 0.0
            else:
                record.duration = 0.0

    @api.depends('attendance_ids.attendance_status')
    def _occupation_percent_count(self):
        for record in self:
            present_count = len(record.attendance_ids.filtered(lambda a: a.attendance_status == 'present'))
            if record.session_id and record.session_id.seats > 0:
                record.occupation_percent = (present_count / record.session_id.seats) * 100
            else:
                record.occupation_percent = 0.0

    @api.depends('date_day', 'start_hour', 'end_hour')
    def _compute_unavailable_rooms(self):
        for record in self:
            if record.date_day and record.start_hour and record.end_hour:
                current_id = record._origin.id if record._origin else False
                overlapping = self.env['formation.seance'].search([
                    ('id', '!=', current_id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour),
                    ('session_id.state', 'in', ['confirmed', 'in_progress'])
                ])
                record.unavailable_room_ids = overlapping.mapped('room_id')
            else:
                record.unavailable_room_ids = False

    # =========================================================================
    # 3. CONTRAINTES DE VALIDATION (@api.constrains)
    # =========================================================================
    @api.constrains('start_hour', 'end_hour')
    def _check_dates(self):
        for record in self:
            if record.start_hour and record.end_hour:
                if record.end_hour < record.start_hour:
                    raise ValidationError("L'heure de fin ne peut pas être antérieure à l'heure de début !")
                if record.start_hour == record.end_hour:
                    raise ValidationError("L'heure de début et de fin ne peuvent pas être identiques.")
                if (record.end_hour - record.start_hour) > 12:
                    raise ValidationError("Une séance ne peut pas durer plus de 12 heures !")

    @api.constrains('date_day', 'start_hour', 'end_hour', 'session_id', 'room_id')
    def _check_seance_constraints(self):
        for record in self:
            if not (record.date_day and record.start_hour and record.end_hour):
                continue

            # 1. Chevauchement au sein de la même session
            if record.session_id:
                session_overlap = self.search([
                    ('id', '!=', record.id),
                    ('session_id', '=', record.session_id.id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour)
                ], limit=1)
                if session_overlap:
                    raise ValidationError(
                        f"Conflit de session : Les séances d'une même session ne peuvent pas se chevaucher. "
                        f"Une séance existe déjà de {session_overlap.start_hour}h à {session_overlap.end_hour}h."
                    )

            # 2. Maintenance et chevauchement de salle
            if record.room_id:
                if record.room_id.admin_state == 'maintenance':
                    raise ValidationError(
                        f"Impossible de réserver : La salle '{record.room_id.name}' est en maintenance."
                    )

                room_overlap = self.search([
                    ('id', '!=', record.id),
                    ('room_id', '=', record.room_id.id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour),
                    ('session_id.state', 'in', ['confirmed', 'in_progress'])
                ], limit=1)
                if room_overlap:
                    raise ValidationError(
                        f"La salle {record.room_id.name} est déjà occupée le {record.date_day} "
                        f"entre {room_overlap.start_hour}h et {room_overlap.end_hour}h !"
                    )

    @api.constrains('room_id', 'session_id')
    def _check_room_capacity(self):
        for record in self:
            if record.room_id and record.session_id:
                participants_count = len(record.session_id.registration_ids)
                room_capacity = record.room_id.capacity
                if participants_count > room_capacity:
                    raise ValidationError(
                        f"Capacité de salle insuffisante ! La session '{record.session_id.name}' "
                        f"compte actuellement {participants_count} inscrits, mais la salle '{record.room_id.name}' "
                        f"ne peut en accueillir que {room_capacity}."
                    )

    @api.constrains('date_day', 'session_id')
    def _check_date_within_session(self):
        for record in self:
            if record.date_day and record.session_id:
                session = record.session_id
                if session.date_start and record.date_day < session.date_start:
                    raise ValidationError(
                        f"Erreur de date : La séance est prévue le {record.date_day}, "
                        f"mais la session '{session.name}' ne commence que le {session.date_start}."
                    )
                if session.date_end and record.date_day > session.date_end:
                    raise ValidationError(
                        f"Erreur de date : La séance est prévue le {record.date_day}, "
                        f"mais la session '{session.name}' se termine le {session.date_end}."
                    )

    @api.constrains('session_id')
    def _check_session_status_for_seance(self):
        for record in self:
            if record.session_id and record.session_id.state in ['cancelled', 'postponed']:
                raise ValidationError(
                    f"Action interdite : Vous ne pouvez pas planifier ou modifier une séance "
                    f"car la session '{record.session_id.name}' est actuellement "
                    f"{dict(record.session_id._fields['state'].selection).get(record.session_id.state)}."
                )

    @api.constrains('date_day', 'start_hour', 'end_hour', 'session_id')
    def _check_instructor_double_booking(self):
        for record in self:
            if record.start_hour and record.end_hour and record.session_id and record.session_id.instructor_id:
                current_instructor = record.session_id.instructor_id.id
                overlapping_seance = self.search([
                    ('id', '!=', record.id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour),
                    ('session_id.instructor_id', '=', current_instructor),
                    ('session_id.state', 'not in', ['cancelled', 'draft'])
                ])
                if overlapping_seance:
                    raise ValidationError(
                        f"Conflit d'emploi du temps ! Le formateur '{record.session_id.instructor_id.name}' "
                        f"ne peut pas assurer cette séance. Il anime déjà la session "
                        f"'{overlapping_seance[0].session_id.name}' le {record.date_day} "
                        f"entre {overlapping_seance[0].start_hour}h et {overlapping_seance[0].end_hour}h."
                    )

    # =========================================================================
    # 4. SURCHARGE DES MÉTHODES ORM (CRUD)
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seances = super(FormationSeance, self).create(vals_list)
        for seance in seances:
            participants = seance.session_id.registration_ids
            for reg in participants:
                self.env['formation.attendance'].create({
                    'seance_id': seance.id,
                    'registration_id': reg.id,
                })
        return seances