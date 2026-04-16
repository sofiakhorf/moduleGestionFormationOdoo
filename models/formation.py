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


class FormationAttendance(models.Model):
    _name = 'formation.attendance'
    _description = 'Association Posséde (Présences)'

    seance_id = fields.Many2one('formation.seance', string="Séance", required=True)
    partner_id = fields.Many2one('res.partner', string="Participant", required=True)
    
    # Attribut porté par l'association 'posséde'
    attendance_status = fields.Selection([
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'En retard')
    ], string="Statut Présence", default='present')

    # On ajoute la date de la séance en champ lié (related) pour faciliter les recherches/filtres
    # Champ lié pour l'affichage et les filtres
    date_day = fields.Date(related='seance_id.date_day', store=True, string="Date Séance")





