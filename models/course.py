
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FormationCourse(models.Model):
    _name = 'formation.course'
    _description = 'Formation'

    name = fields.Char("Titre de la formation", required=True)
    description = fields.Text("Description")
    level = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé')
    ], string="Niveau")
    duration = fields.Integer("Durée (Heures)")

    # Relation Many2many (Association 'enseigner')
 


    instructor_ids = fields.Many2many(
            'res.partner',
            relation='formation_course_instructor_rel',
            column1='course_id',
            column2='partner_id',
            string="Formateurs habilités",
            domain=[('is_instructor', '=', True)]
        )