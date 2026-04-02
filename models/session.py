from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FormationSession(models.Model):
    _name = 'formation.session'
    _description = 'Session'

    name = fields.Char("Nom de la Session", required=True)
    date_start = fields.Date("Date Début")
    date_end = fields.Date("Date Fin")
    seats = fields.Integer("Nombre de places" ,store=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('done', 'Terminée')
    ], string="Statut", default='draft')

    



    # Relations Many2one
    course_id = fields.Many2one('formation.course', string="Formation", required=True)
    instructor_id = fields.Many2one('res.partner', string="Formateur") # Ajoute domain plus tard
 

    # Relations One2many
    registration_ids = fields.One2many('formation.registration', 'session_id', string="Inscriptions")
    seance_ids = fields.One2many('formation.seance', 'session_id', string="Séances")

    # --- AJOUT DE L'API ODOO ---

    # 1. Calcul du taux d'occupation (Progress Bar)
    taken_seats_percent = fields.Float(string="Occupation (%)", compute='_compute_taken_seats')

    @api.depends('seats', 'registration_ids')
    def _compute_taken_seats(self):
        for record in self:
            if not record.seats:
                record.taken_seats_percent = 0.0
            else:
                # On compte le nombre d'IDs dans la liste des inscriptions
                record.taken_seats_percent = 100.0 * len(record.registration_ids) / record.seats

    # 2. Contrainte de cohérence des dates
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError("La date de fin ne peut pas être antérieure à la date de début !")
            



   


