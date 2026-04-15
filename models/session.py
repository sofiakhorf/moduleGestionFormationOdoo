from odoo import models, fields, api
from datetime import date, timedelta
from odoo.exceptions import ValidationError

class FormationSession(models.Model):
    _name = 'formation.session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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

    # On crée un champ Many2many "virtuel" (calculé) pour afficher toutes les salles de la session
    room_ids = fields.Many2many(
        'formation.room', 
        string="Salles utilisées", 
        compute='_compute_room_ids',
        # store=True # Décommente cette ligne si tu as besoin de chercher une session par salle dans la barre de recherche Odoo
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('postponed', 'Reportée'),
        ('done', 'Terminée'),
        ('cancelled', 'Annulée'),
    ], string="Statut", default='draft', tracking=True)

    @api.constrains('state')
    def _check_requirements_on_state_change(self):
        """ 
        Vérifie les règles métier lors de l'activation d'une session (Confirmée ou En cours).
        """
        for session in self:
            if session.state in ['confirmed', 'in_progress']:
                # 1. Règle : Dates de début et de fin obligatoires
                if not session.date_start or not session.date_end:
                    raise ValidationError("Impossible de confirmer : Les dates de début et de fin doivent être renseignées.")
                
                # 2. Règle : Durée formation == Somme durée séances
                # On calcule la somme des durées (fin - début) de chaque séance
                total_seances_duration = sum((seance.end_hour - seance.start_hour) for seance in session.seance_ids if seance.start_hour and seance.end_hour)
                course_duration = session.course_id.duration
                
                if total_seances_duration > course_duration:
                    raise ValidationError(
                        f"Incohérence de durée : La formation '{session.course_id.name}' dure {course_duration}h, "
                        f"mais le total actuel de vos séances est superieure à la date pemise c'est à dire  {total_seances_duration}h. "
                        f"Veuillez ajuster les séances avant de confirmer."
                    )

                # 3. Vérification des conflits de salle
        
        
        """ 
        Si on active une session (Confirmée/En cours), on vérifie que ses séances 
        ne créent pas de conflits avec d'autres sessions déjà actives.
        """
        for session in self:
            if session.state in ['confirmed', 'in_progress']:
                for seance in session.seance_ids:
                    # On appelle la logique de vérification de la séance
                    # Si un conflit existe, le ValidationError remontera ici
                    seance._check_room_availability_and_state()


    @api.depends('seance_ids.room_id')
    def _compute_room_ids(self):
        for session in self:
            # La méthode .mapped() est ultra-optimisée dans Odoo. 
            # Elle parcourt toutes les séances de la session et extrait les salles uniques.
            session.room_ids = session.seance_ids.mapped('room_id')

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



# --- MÉTHODE CERVEAU (Centralise toute la logique) ---
    def _apply_state_logic(self):
        """ Détermine l'état et lance les alertes en fonction des dates """
        today = fields.Date.today()
        for record in self:
            if not record.date_start:
                continue

            # A. LOGIQUE DES ALERTES (Uniquement si en brouillon)
            if record.state == 'draft':
                if record.date_start == today + timedelta(days=1):
                    record._create_admin_activity("Alerte J-1 : Session toujours en Brouillon.")
                elif record.date_start <= today:
                    record._create_admin_activity("URGENT : Date de début atteinte (Session en Brouillon).")

            # B. LOGIQUE DE CHANGEMENT D'ÉTAT (Automatique)
            new_state = False
            # Cas 1 : Passage à "En cours"
            if record.state == 'confirmed' and record.date_start <= today:
                new_state = 'in_progress'
            
            # Cas 2 : Passage à "Terminé"
            elif record.state == 'in_progress' and record.date_end and record.date_end < today:
                new_state = 'done'

            # Cas 3 : Retour arrière (Si on modifie les dates manuellement)
            elif record.state == 'done' and record.date_end and record.date_end >= today:
                new_state = 'in_progress'
            elif record.state == 'in_progress' and record.date_start > today:
                new_state = 'confirmed'

            if new_state:
                record.state = new_state
                # On retourne l'info pour le Toast si c'est un appel manuel
                return new_state 

    # --- POINTS D'ENTRÉE (Appellent le cerveau) ---

    def write(self, vals):
        res = super(FormationSession, self).write(vals)
        
        if 'date_start' in vals or 'date_end' in vals or 'state' in vals:
            for record in self:
                # On capture l'état avant et après
                old_state = record.state
                changed_state = record._apply_state_logic()
                
                # On prépare un message de succès
                message = "Dates mises à jour."
                if changed_state:
                    message = f"Statut mis à jour : {record.state}"
                elif record.state == 'draft':
                    message = "Vérification des alertes effectuée (J-1)."

                # On force le retour de la notification pour TESTER
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
        """ Déclencheur automatique de nuit (CRON) """
        sessions = self.search([('state', 'not in', ['done', 'cancelled'])])
        sessions._apply_state_logic()

    def _create_admin_activity(self, note):
        # On prend l'utilisateur actuel 
        target_user = self.env.user 
        
        # 1. Poster dans le log (le plus fiable pour tester)
        self.message_post(
            body=f"<b>LOG ALERTE :</b> {note}",
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        # 2. Créer l'activité
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            note=note,
            user_id=target_user.id,
            summary="Alerte Session"
        )

    @api.constrains('seats', 'registration_ids')
    def _check_seats_limit(self):
        """
        Règle : Le nombre de participants inscrits ne doit pas dépasser la limite de places.
        """
        for record in self:
            # On vérifie uniquement si une limite de place a été définie (> 0)
            if record.seats > 0 and len(record.registration_ids) > record.seats:
                raise ValidationError(
                    f"Surréservation ! Le nombre de participants actuels ({len(record.registration_ids)}) "
                    f"dépasse le nombre de places maximum autorisé ({record.seats}) pour cette session."
                )

