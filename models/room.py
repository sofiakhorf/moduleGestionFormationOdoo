from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FormationRoom(models.Model):
    _name = 'formation.room'
    _description = 'Salle de Formation'

    name = fields.Char(string="Nom de la salle", required=True)
    capacity = fields.Integer(string="Capacité (Places)", required=True)
    location = fields.Char(string="Emplacement / Bâtiment")


    # État de la salle : Disponible ou en Travaux
    state = fields.Selection([
        ('available', 'Disponible'),
        ('maintenance', 'En Travaux / Maintenance')
    ], string="Statut de la salle", default='available', required=True)
    
    # Relation pour voir quelles sessions occupent cette salle
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

    @api.constrains('capacity')
    def _check_capacity_positive(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError("La capacité de la salle doit être supérieure à zéro.")
            
