from odoo import models, fields

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
    instructor_ids = fields.Many2many('res.partner', string="Formateurs habilités", domain=[('is_instructor', '=', True)])

class FormationRoom(models.Model):
    _name = 'formation.room'
    _description = 'Salle'

    name = fields.Char("Numéro de salle", required=True)
    is_available = fields.Boolean("Disponible", default=True)

class FormationSession(models.Model):
    _name = 'formation.session'
    _description = 'Session'

    name = fields.Char("Nom de la Session", required=True)
    date_start = fields.Date("Date Début")
    date_end = fields.Date("Date Fin")
    seats = fields.Integer("Nombre de places")
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('done', 'Terminée')
    ], string="Statut", default='draft')

    # Relations 1,1 et 0,1 (Many2one)
    course_id = fields.Many2one('formation.course', string="Formation", required=True)
    instructor_id = fields.Many2one('res.partner', string="Formateur", domain=[('is_instructor', '=', True)])
    room_id = fields.Many2one('formation.room', string="Salle")

    #pour povoir consulter la liste des paticipant  et les seance de chanue session à partir de l'onglet session
    registration_ids = fields.One2many('formation.registration', 'session_id', string="Inscriptions")
    seance_ids = fields.One2many('formation.seance', 'session_id', string="Séances")

class FormationRegistration(models.Model):
    _name = 'formation.registration'
    _description = 'Association Inscrire'

    session_id = fields.Many2one('formation.session', string="Session", required=True)
    partner_id = fields.Many2one('res.partner', string="Participant", domain=[('is_student', '=', True)], required=True)
    
    # Attributs portés par l'association 'inscrire'
    project_theme = fields.Char("Thème du projet")
    project_link = fields.Char("Lien du projet")
    submission_date = fields.Date("Date de soumission")
    evaluation = fields.Float("Évaluation")
    status = fields.Selection([
        ('registered', 'Inscrit'),
        ('cancelled', 'Annulé')
    ], string="Statut Inscription", default='registered')

class FormationSeance(models.Model):
    _name = 'formation.seance'
    _description = 'Séance'

    date_day = fields.Date("Date du jour", required=True)
    start_hour = fields.Float("Heure Début")
    end_hour = fields.Float("Heure Fin")
    
    # Relation 1,1 (Association 'composer')
    session_id = fields.Many2one('formation.session', string="Session", required=True)

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