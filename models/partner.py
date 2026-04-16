from odoo import models, fields
#On importe la structure nécessaire pour créer des tables en base de données ET  On importe les types de colonnes (Texte, Date, Booléen, etc.)

class ResPartner(models.Model):#un modèle de base de données Odoo
    _inherit = 'res.partner'

    # Rôles (pour filtrage dans les vues)
    is_instructor = fields.Boolean("Est un formateur")
    #Crée une case à cocher (True/False) en base de données.
    is_student = fields.Boolean("Est un participant")

    # Attributs spécifiques au Formateur (MCD)
    expertise = fields.Text("Expertise")
    diploma = fields.Char("Diplôme")

    # Relation Many2many (Inverse) pour voir les cours depuis la fiche formateur
    course_ids = fields.Many2many(
        'formation.course',
        relation='formation_course_instructor_rel',
        column1='partner_id',
        column2='course_id',
        string="Cours autorisés à enseigner"
    )
    
    